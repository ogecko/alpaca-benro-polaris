# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_2_Composite.py
# Version: 2.0.1
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# Description
# -----------
# Scans the Siril home directory for stacked channel subdirectories and
# automatically selects the composite mode based on what is available:
#
#   LRGB  -- L/R/G/B stacked dirs -> luminance + colour composition
#   SHO   -- Ha/Sii/Oiii stacked dirs -> Hubble palette (SII=R Ha=G OIII=B)
#   HSO   -- as SHO but Ha=R SII=G OIII=B (set COMPOSITE_MODE manually)
#
# For each GLAT/GLON prefix where all required channels have a matching
# _stack.fits file, this script:
#
#   1.  Align channels -- register against reference (homography with fallbacks)
#   2.  Compose        -- rgbcomp (LRGB with luminance, or RGB for narrowband)
#   3.  Save GLATnnnX_GLONnnn_(LRGB|SHO|HSO).fits into composites/ subdir
#
# After this script completes -- BEFORE running Galactic_3_Stretch.py:
#
#   Step A: Batch plate-solve all process/GLAT*_LRGB.fits with ASTAP.
#           In ASTAP: File -> Batch plate-solve, point at the process/
#           folder and solve all _LRGB.fits files. ASTAP writes the WCS
#           solution back into each FITS header. This is required for
#           SPCC colour calibration in Galactic_3_Stretch.py.
#
#   Step B: Crop the border artifacts from each plate-solved _LRGB.fits.
#           After LRGB composition the edges contain registration
#           border artifacts -- black or noisy triangular corners where
#           the four channels did not fully overlap after alignment
#           (each channel shift is slightly different, leaving uncovered
#           corner regions with no data or data from only some channels).
#           Open each _LRGB.fits in Siril, draw a crop selection that
#           removes these borders and save. Use a consistent crop margin
#           (e.g. 100px on each side) across all panels -- uneven borders
#           will create visible seams when the panels are mosaicked.
#
# Prerequisites
# -------------
#   Siril 1.4.0 or later.
#   ASTAP installed with a star database (D50 recommended).
#
# Usage
# -----
#   Set Siril home directory to the session root (containing L/, R/, G/, B/).
#   Run from Scripts menu.  The script processes each GLAT/GLON panel in turn.
#
# Output files (all in <home>/composites/):
#   GLATnnnX_GLONnnn_LRGB.fits    (linear composite, ready for ASTAP + crop)

import sirilpy as s
import traceback
from pathlib import Path
from collections import defaultdict

# ---------------------------------------------------------------------------
# CONFIGURATION -- edit these values as needed
# ---------------------------------------------------------------------------

# COMPOSITE MODE -- determines which filters are combined and how.
#
# "LRGB" : Luminance + RGB broadband (L as lum, R/G/B as colour).
#           Auto-selected when L/R/G/B stacked dirs are present.
#           SPCC uses wideband (solar analogue) photometry.
#
# "SHO"  : Hubble/HST palette -- SII=R, Ha=G, OIII=B.
#           Auto-selected when Ha/Sii/Oiii dirs are present and LRGB absent.
#           SPCC uses narrowband (7nm) photometry.
#           NOTE: This is the standard Hubble Space Telescope palette.
#
# "HSO"  : Ha=R, SII=G, OIII=B -- alternative narrowband mapping.
#           Select manually to override auto-detection.
#           SPCC uses narrowband (7nm) photometry.
#           NOTE: For best results with HSO, use VeraLux Alchemy for
#           colour remapping before running Galactic_3_Stretch.py.
#
# Set to None to auto-detect from available stacked directories.
COMPOSITE_MODE = None   # None = auto-detect, or "LRGB" / "HSO" / "SHO"

# Channel directories per composite mode (relative to Siril home directory)
# Keys match what rgbcomp expects: for LRGB -- L (lum), R, G, B (colour).
# For narrowband -- the filter names map to R/G/B display channels.
CHANNEL_DIRS_LRGB = {
    "L":  "L/stacked",
    "R":  "R/stacked",
    "G":  "G/stacked",
    "B":  "B/stacked",
}
CHANNEL_DIRS_SHO = {        # Hubble palette: SII->R, Ha->G, OIII->B
    "R":  "Sii/stacked",
    "G":  "Ha/stacked",
    "B":  "Oiii/stacked",
}
CHANNEL_DIRS_HSO = {        # Alternative: Ha->R, SII->G, OIII->B
    "R":  "Ha/stacked",
    "G":  "Sii/stacked",
    "B":  "Oiii/stacked",
}

# Input file suffix to look for in each channel directory
INPUT_SUFFIX = "_stack"      # e.g. GLAT007N_GLON344_stack.fits
FITS_EXTENSIONS = (".fits", ".fit", ".fts")

# First N characters of filename used as the panel prefix key
PREFIX_LENGTH = 16   # e.g. "GLAT007N_GLON344"

# Output suffixes per composite mode -- written into process/ subdir
SUFFIX_BY_MODE = {
    "LRGB": "_LRGB",
    "HSO":  "_HSO",
    "SHO":  "_SHO",
}

STARNET_STARMASK_PREFIX = "starmask_"

# ---------------------------------------------------------------------------
# Optional border crop -- removes registration/compositing artifacts at the
# panel edges (see "Step B" in the header comment above: the corners/edges
# where L/R/G/B didn't all perfectly overlap after independent registration,
# leaving black or partial-colour borders). Doing this here, before ASTAP
# plate-solving, is safe -- there's no WCS in the file yet at this point, so
# there's nothing to invalidate, and it also means you can skip the manual
# "Step B" crop afterward if you enable this.
RUN_CROP = True
CROP_MODE = "auto"    # "fixed" | "auto" | "auto_or_fixed_min"
                       #   "fixed": always crop CROP_FIXED_PERCENT from every edge.
                       #   "auto": detect the artifact border automatically per
                       #     edge (see CROP_AUTO_* below) and crop exactly that,
                       #     independently per side.
                       #   "auto_or_fixed_min": auto-detect, but never crop less
                       #     than CROP_FIXED_PERCENT even if auto-detection finds
                       #     a smaller (or no) artifact -- a safety floor.
CROP_FIXED_PERCENT = 2.5   # percent of width/height cropped from EACH edge in
                           # "fixed" mode, or the floor in "auto_or_fixed_min".

# Auto-detection: a pixel counts as a compositing artifact if ANY channel is
# at/near exactly 0 there (real background noise in linear data is never
# exactly 0.0, so this is a reliable signal for "at least one channel had no
# data here after registration"). Scans inward from each edge row/column at a
# time; an edge stops being "bad" once CROP_AUTO_CONSECUTIVE_GOOD rows/columns
# in a row fall below CROP_AUTO_INVALID_FRAC.
CROP_AUTO_INVALID_FRAC = 0.02        # fraction of a row/column allowed to be
                                     # zero-in-any-channel before that row/
                                     # column still counts as "artifact"
CROP_AUTO_CONSECUTIVE_GOOD = 5       # consecutive clean rows/columns needed
                                     # before declaring that edge's artifact
                                     # zone has ended
CROP_AUTO_MAX_PERCENT = 10.0         # safety cap -- auto-detection can never
                                     # crop more than this from any one edge,
                                     # regardless of what it finds
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# DEBUG -- set True to keep _lrgb_align_* temp directories for inspection
DEBUG_KEEP_TEMP = False
# ---------------------------------------------------------------------------


def detect_composite_mode(home_dir):
    """
    Auto-detect composite mode from available stacked directories.
    Returns "LRGB", "HSO", or None if insufficient channels found.
    """
    if COMPOSITE_MODE is not None:
        return COMPOSITE_MODE

    def has_channel(rel_dir):
        d = home_dir / rel_dir
        return d.is_dir() and any(
            p.suffix.lower() in FITS_EXTENSIONS and INPUT_SUFFIX in p.stem
            for p in d.iterdir() if p.is_file()
        )

    has_L = has_channel("L/stacked")
    has_R = has_channel("R/stacked")
    has_G = has_channel("G/stacked")
    has_B = has_channel("B/stacked")
    has_Ha  = has_channel("Ha/stacked")
    has_Sii = has_channel("Sii/stacked")
    has_Oiii = has_channel("Oiii/stacked")

    if has_L and has_R and has_G and has_B:
        return "LRGB"
    if has_Ha and has_Sii and has_Oiii:
        return "SHO"   # Hubble palette default for narrowband
    return None


def siril_log(siril, msg):
    """Log a plain-ASCII message to the Siril console."""
    safe = msg.encode("ascii", errors="replace").decode("ascii")
    if not safe.strip():
        safe = " "
    siril.log(safe)


def _quote_if_needed(arg):
    """
    Wrap an argument in double quotes if it contains whitespace, so Siril's
    command-line parser treats it as a single token instead of splitting on
    the internal space (e.g. Windows paths like 'D:\\...\\HIP 97434\\...').

    IMPORTANT: Siril only recognises a quoted token when the double-quote is
    the very FIRST character of that token. Quoting only the value portion
    of a '-key=value' style option (e.g. -out="C:\\a b") does NOT work --
    Siril still splits on the internal space and leaves a stray quote
    character glued to the truncated path. The quote has to wrap the
    ENTIRE token, prefix included (e.g. "-out=C:\\a b"), so it is the
    leading character of the token Siril sees.

    Arguments that are already quoted, or that contain no whitespace, are
    returned unchanged.
    """
    txt = str(arg)
    if " " not in txt and "\t" not in txt:
        return txt
    if txt.startswith('"') and txt.endswith('"'):
        return txt
    return '"' + txt + '"'


def cmd_safe(siril, *args):
    """Run a Siril command; return True on success, False on failure."""
    args = tuple(_quote_if_needed(a) for a in args)
    try:
        siril.cmd(*args)
        return True
    except Exception as exc:
        siril_log(siril, "  [WARNING] Command failed: " + " ".join(str(a) for a in args))
        siril_log(siril, "            " + str(exc))
        return False


def find_panel_files(home_dir, mode, channel_dirs):
    """
    Scan stacked directories for stack_denoised files.

    mode        : "LRGB", "HSO", or "SHO"
    channel_dirs: dict mapping channel key -> relative dir (from CHANNEL_DIRS_*)

    Returns a dict:
        { prefix_16char: { channel_key: Path, ... } }
    Only entries where ALL required channels are present are included.
    """
    channel_map = {}
    for channel, rel_dir in channel_dirs.items():
        channel_map[channel] = {}
        search_dir = home_dir / rel_dir
        if not search_dir.is_dir():
            continue
        for p in sorted(search_dir.iterdir()):
            if not p.is_file():
                continue
            if p.suffix.lower() not in FITS_EXTENSIONS:
                continue
            if INPUT_SUFFIX not in p.stem:
                continue
            if len(p.name) < PREFIX_LENGTH:
                continue
            prefix = p.name[:PREFIX_LENGTH]
            channel_map[channel][prefix] = p

    # Intersect: only prefixes present in ALL channels
    required = list(channel_dirs.keys())
    if not required:
        return {}
    all_prefixes = set(channel_map[required[0]].keys())
    for ch in required[1:]:
        all_prefixes &= set(channel_map[ch].keys())

    panels = {}
    for prefix in sorted(all_prefixes):
        panels[prefix] = {ch: channel_map[ch][prefix] for ch in required}
    return panels


def _find_edge_margin(invalid_frac, max_margin, threshold, consecutive_good):
    """
    Scan a 1D array of per-row (or per-column) "invalid fraction" values
    from index 0 inward, looking for where the artifact border ends --
    defined as the first point with `consecutive_good` rows/columns in a
    row falling at/below `threshold`. Returns the margin (number of rows/
    columns to crop from that edge), capped at max_margin.
    """
    n = len(invalid_frac)
    good_streak = 0
    limit = min(n, max_margin + consecutive_good)
    for i in range(limit):
        if invalid_frac[i] <= threshold:
            good_streak += 1
            if good_streak >= consecutive_good:
                margin = i - consecutive_good + 1
                return max(margin, 0)
        else:
            good_streak = 0
    return max_margin


def detect_autocrop_margins(data, invalid_frac=CROP_AUTO_INVALID_FRAC,
                            consecutive_good=CROP_AUTO_CONSECUTIVE_GOOD,
                            max_percent=CROP_AUTO_MAX_PERCENT, iterations=6):
    """
    Detect how much to crop from each of the 4 edges to remove compositing
    artifacts -- a pixel counts as an artifact if ANY channel is at/near
    exactly 0 there (real background noise in linear data is never exactly
    0.0, so this reliably flags "at least one channel had no data here
    after registration", which is exactly what a misaligned-channel border
    looks like). Returns (top, bottom, left, right) margins in pixels.

    Coordinate-descent refinement: a channel shifted purely horizontally
    leaves a full-HEIGHT invalid column strip, which would contaminate
    every row's invalid fraction if measured against the full image and
    confuse the top/bottom scan into thinking the whole image is bad (and
    vice versa for a vertical-only shift confusing the left/right scan).
    Each iteration recomputes top/bottom using the CURRENT left/right
    crop to exclude that contamination, then recomputes left/right using
    the current top/bottom -- repeated until the margins stop changing.
    Margins are recomputed fresh each pass (not accumulated), so an
    overshoot from an early, still-contaminated pass gets corrected once
    the contaminating axis is excluded, rather than being locked in.
    """
    import numpy as np
    n_ch, H, W = data.shape
    max_v = int(H * max_percent / 100.0)
    max_h = int(W * max_percent / 100.0)

    top = bottom = left = right = 0
    for _ in range(iterations):
        # Recompute top/bottom using the CURRENT left/right crop.
        w_lo, w_hi = left, W - right
        if w_hi - w_lo < 10:
            break
        row_invalid = (data[:, :, w_lo:w_hi] <= 1e-9).any(axis=0).mean(axis=1)
        new_top = _find_edge_margin(row_invalid, max_v, invalid_frac, consecutive_good)
        new_bottom = _find_edge_margin(row_invalid[::-1], max_v, invalid_frac, consecutive_good)

        # Recompute left/right using the just-updated top/bottom crop.
        h_lo, h_hi = new_top, H - new_bottom
        if h_hi - h_lo < 10:
            break
        col_invalid = (data[:, h_lo:h_hi, :] <= 1e-9).any(axis=0).mean(axis=0)
        new_left = _find_edge_margin(col_invalid, max_h, invalid_frac, consecutive_good)
        new_right = _find_edge_margin(col_invalid[::-1], max_h, invalid_frac, consecutive_good)

        converged = (new_top == top and new_bottom == bottom
                    and new_left == left and new_right == right)
        top, bottom, left, right = new_top, new_bottom, new_left, new_right
        if converged:
            break

    top = min(top, max_v)
    bottom = min(bottom, max_v)
    left = min(left, max_h)
    right = min(right, max_h)
    return top, bottom, left, right


def apply_crop(fits_path, mode=CROP_MODE, fixed_percent=CROP_FIXED_PERCENT):
    """
    Crop a composite FITS file in place to remove registration/compositing
    border artifacts (see the "Optional border crop" config comment for
    why this is safe to do before ASTAP plate-solving). Returns
    (ok, top, bottom, left, right) -- the margins actually applied, in
    pixels, for logging.
    """
    try:
        import numpy as np
        from astropy.io import fits as _afits

        with _afits.open(str(fits_path)) as hdul:
            header = hdul[0].header.copy()
            data = hdul[0].data.astype(np.float32)

        mono = data.ndim == 2
        if mono:
            data = data[np.newaxis]
        n_ch, H, W = data.shape

        if mode == "fixed":
            top = bottom = int(H * fixed_percent / 100.0)
            left = right = int(W * fixed_percent / 100.0)
        else:
            top, bottom, left, right = detect_autocrop_margins(data)
            if mode == "auto_or_fixed_min":
                floor_v = int(H * fixed_percent / 100.0)
                floor_h = int(W * fixed_percent / 100.0)
                top = max(top, floor_v)
                bottom = max(bottom, floor_v)
                left = max(left, floor_h)
                right = max(right, floor_h)

        if top + bottom >= H or left + right >= W:
            return False, 0, 0, 0, 0

        cropped = data[:, top:H - bottom, left:W - right]
        if mono:
            cropped = cropped[0]

        out_hdu = _afits.PrimaryHDU(cropped, header=header)
        out_hdu.writeto(str(fits_path), overwrite=True)
        return True, top, bottom, left, right

    except Exception:
        return False, 0, 0, 0, 0


def process_panel(siril, prefix, files, home_dir, mode):
    """
    Run the full LRGB pipeline for one panel prefix.
    Returns True on success, False on failure.
    """
    siril_log(siril, " ")
    siril_log(siril, "=" * 60)
    siril_log(siril, "Panel: " + prefix + "  [" + mode + "]")
    for ch, f in files.items():
        siril_log(siril, "  " + ch + ": " + f.name)
    siril_log(siril, "=" * 60)

    # Composites go into composites/ -- clean separation from stretch intermediates
    composites_dir = home_dir / "composites"
    composites_dir.mkdir(exist_ok=True)

    composite_suffix = SUFFIX_BY_MODE[mode]
    lrgb_out = composites_dir / (prefix + composite_suffix + ".fits")

    # Skip if composite already exists in composites/
    # (Galactic_3 skip is separate -- it checks for _stretched_result in result_fits/)
    if lrgb_out.exists():
        siril_log(siril, "  SKIP: already composed: " + lrgb_out.name)
        siril_log(siril, "  (Delete from composites/ to recompose)")
        return True

    # No stale cleanup -- composites/ keeps files for diagnosis

    # ------------------------------------------------------------------
    # Step 1: Align channels then LRGB compose
    #
    # rgbcomp has NO built-in alignment -- it is purely a pixel combiner.
    # The correct approach (per Siril docs) is to:
    #   a) Build a 4-image sequence (L, R, G, B stacks)
    #   b) Register them against each other (L as reference)
    #   c) Feed the registered r_ files to rgbcomp
    #
    # We use a temporary work directory to avoid polluting the home dir
    # with sequence files, then clean it up afterwards.
    # ------------------------------------------------------------------
    siril_log(siril, "  [1/8] Aligning channels then LRGB composition...")

    if not cmd_safe(siril, "cd", str(home_dir)):
        return False

    # Create a clean temp directory for alignment work
    import shutil as _shutil
    align_dir = home_dir / ("_lrgb_align_" + prefix)
    if align_dir.exists():
        _shutil.rmtree(align_dir, ignore_errors=True)
    align_dir.mkdir(parents=True, exist_ok=True)

    if not cmd_safe(siril, "cd", str(align_dir)):
        return False

    # Copy each channel into the align dir with a clear filter-named sequence.
    # Each channel is a single-frame sequence named after its filter:
    #   L_00001.<ext>, R_00001.<ext>, G_00001.<ext>, B_00001.<ext>
    # After registration against L, Siril writes:
    #   r_L_00001.<ext>  (L reference -- copy of original, no transform)
    #   r_R_00001.<ext>, r_G_00001.<ext>, r_B_00001.<ext>  (aligned to L)
    # This naming makes it immediately obvious which file is which if you
    # need to inspect the temp dir after an interrupted run.
    #
    # Strategy: build a 4-frame sequence where each frame is named with
    # its filter letter as the sequence basename, padded to 5 digits.
    # To get named registered outputs we register each colour channel as
    # a 2-frame sequence paired with L, so the r_ prefix is filter-labelled.
    # Siril always names the registered output r_<seqname>_NNNNN.<ext>.
    # We therefore use three 2-frame sequences: LR, LG, LB -- each with L
    # as frame 1 (reference).  This gives r_LR_00001 (L), r_LR_00002 (R),
    # r_LG_00002 (G), r_LB_00002 (B), all clearly labelled.

    # Determine reference and colour channels from mode
    if mode == "LRGB":
        # L is the luminance reference; R/G/B are colour channels
        ref_ch        = "L"
        colour_channels = ["R", "G", "B"]
    else:
        # Narrowband: use G as the reference (Ha in SHO, Sii in HSO).
        # All three filters are aligned in one pass: R and B align to G.
        # This gives a single consistent registration across all channels.
        ref_ch        = "G"
        colour_channels = ["R", "B"]

    src_ext = files[ref_ch].suffix
    ext_no_dot = src_ext.lstrip(".")
    cmd_safe(siril, "setext", ext_no_dot)

    # Copy reference channel
    ref_copy = align_dir / (ref_ch + "_00001" + src_ext)
    try:
        _shutil.copy2(files[ref_ch], ref_copy)
    except Exception as exc:
        siril_log(siril, "  [ERROR] Could not copy " + ref_ch + " channel: " + str(exc))
        if not DEBUG_KEEP_TEMP:
            _shutil.rmtree(align_dir, ignore_errors=True)
        cmd_safe(siril, "cd", str(home_dir))
        return False
    # Keep backward compat alias
    l_copy = ref_copy

    reg_colour = {}
    for ch_name, ch_file in [(c, files[c]) for c in colour_channels]:
        seq = ref_ch + ch_name        # sequence basename: LR/LG/LB or RG/RB
        ch_copy = align_dir / (ch_name + "_00002" + src_ext)
        try:
            _shutil.copy2(ch_file, ch_copy)
        except Exception as exc:
            siril_log(siril, "  [ERROR] Could not copy " + ch_name
                      + " channel: " + str(exc))
            if not DEBUG_KEEP_TEMP:
                _shutil.rmtree(align_dir, ignore_errors=True)
            cmd_safe(siril, "cd", str(home_dir))
            return False

        # Copy reference to match this pair sequence (L_00001 -> LR_00001 etc.)
        l_seq_copy = align_dir / (seq + "_00001" + src_ext)
        try:
            _shutil.copy2(ref_copy, l_seq_copy)
        except Exception as exc:
            siril_log(siril, "  [ERROR] Could not stage L for " + seq
                      + ": " + str(exc))
            if not DEBUG_KEEP_TEMP:
                _shutil.rmtree(align_dir, ignore_errors=True)
            cmd_safe(siril, "cd", str(home_dir))
            return False

        # Rename colour copy to match sequence name (R_00002 -> LR_00002 etc.)
        ch_seq_copy = align_dir / (seq + "_00002" + src_ext)
        ch_copy.rename(ch_seq_copy)

        siril_log(siril, "  Registering " + ch_name + " against L (seq=" + seq + ")...")
        reg_ok = cmd_safe(siril, "register", seq, "-transf=homography")
        if not reg_ok:
            # Homography failed (poor seeing, elongated stars, few matches).
            # Fall back through progressively simpler transforms.
            for fallback in ("affine", "similarity", "shift"):
                siril_log(siril, "  Retrying " + ch_name
                          + " with -transf=" + fallback + "...")
                reg_ok = cmd_safe(siril, "register", seq, "-transf=" + fallback)
                if reg_ok:
                    siril_log(siril, "  Registered " + ch_name
                              + " with fallback -transf=" + fallback)
                    break
        if not reg_ok:
            siril_log(siril, "  [ERROR] Registration failed for channel "
                      + ch_name + " -- all transforms tried.")
            if not DEBUG_KEEP_TEMP:
                _shutil.rmtree(align_dir, ignore_errors=True)
            cmd_safe(siril, "cd", str(home_dir))
            return False

        # Registered colour frame is r_<seq>_00002.<ext>
        r_ch = align_dir / ("r_" + seq + "_00002" + src_ext)
        if not r_ch.exists():
            # Try alternate extension
            for alt in (".fits", ".fit", ".fts"):
                candidate = align_dir / ("r_" + seq + "_00002" + alt)
                if candidate.exists():
                    r_ch = candidate
                    break
            else:
                siril_log(siril, "  [ERROR] Registered " + ch_name
                          + " output not found: " + r_ch.name)
                if not DEBUG_KEEP_TEMP:
                    _shutil.rmtree(align_dir, ignore_errors=True)
                cmd_safe(siril, "cd", str(home_dir))
                return False

        reg_colour[ch_name] = r_ch
        siril_log(siril, "  Registered: " + r_ch.name)

    # Reference channel is used as-is (no transform needed)
    r_ref = ref_copy
    siril_log(siril, "  All channels aligned:")
    siril_log(siril, "    " + ref_ch + "=" + r_ref.name + "  "
              + "  ".join(ch + "=" + p.name for ch, p in reg_colour.items()))

    # ------------------------------------------------------------------
    # Pre-composition linear_match removed.
    #
    # linear_match on raw stacked data causes the red spot problem:
    #   - R and B channels have pixels saturated at max (65535)
    #   - G channel is NOT saturated (observed max 56879)
    #   - linear_match sees R/B clipped at ceiling, G not clipped
    #   - The fit drives R and B upward toward G's higher median
    #   - This amplifies already-clipped pixels, spreading saturation
    #   - Result: orange stars become pure red squares
    #
    # The GUI "Linear Fit" works because it runs on display-scaled data
    # AFTER colour calibration where saturation behaves differently.
    # On raw pre-SPCC stacks it makes saturation worse, not better.
    #
    # SPCC handles colour balance correctly via stellar photometry.
    # We pass the aligned channels directly to rgbcomp without
    # pre-distorting the levels.
    # ------------------------------------------------------------------
    siril_log(siril, "  Channels aligned -- proceeding to rgbcomp (no linear_match).")

    # Compose channels using rgbcomp
    cmd_safe(siril, "cd", str(composites_dir))
    lrgb_stem = prefix + composite_suffix

    if mode == "LRGB":
        # LRGB: luminance from L, colour from R/G/B
        compose_ok = cmd_safe(
            siril,
            "rgbcomp",
            "-lum=" + str(r_ref),
            str(reg_colour["R"]),
            str(reg_colour["G"]),
            str(reg_colour["B"]),
            "-out=" + lrgb_stem,
        )
    else:
        # Narrowband (HSO or SHO): no luminance -- pure RGB composition
        # R/G/B are already mapped to display colours via CHANNEL_DIRS_*
        compose_ok = cmd_safe(
            siril,
            "rgbcomp",
            str(r_ref),              # R channel (Ha or Sii)
            str(reg_colour["G"]),    # G channel (Sii or Ha)
            str(reg_colour["B"]),    # B channel (Oiii)
            "-out=" + lrgb_stem,
        )

    if not compose_ok:
        siril_log(siril, "  [ERROR] Composition failed.")
        if not DEBUG_KEEP_TEMP:
            _shutil.rmtree(align_dir, ignore_errors=True)
        return False

    # Clean up the alignment temp directory
    if not DEBUG_KEEP_TEMP:
        if not DEBUG_KEEP_TEMP:
            _shutil.rmtree(align_dir, ignore_errors=True)
        siril_log(siril, "  Alignment temp dir cleaned up.")
    else:
        siril_log(siril, "  DEBUG: kept temp dir: " + str(align_dir))

    # Find the composed file (Siril writes <stem>.fit or <stem>.fits)
    lrgb_path = None
    for ext in FITS_EXTENSIONS:
        candidate = composites_dir / (lrgb_stem + ext)
        if candidate.exists():
            lrgb_path = candidate
            break
    if lrgb_path is None:
        siril_log(siril, "  [ERROR] LRGB output file not found after composition.")
        return False

    siril_log(siril, "  LRGB composed: " + lrgb_path.name)

    # ------------------------------------------------------------------
    # Step 2: Save LRGB composite.
    # Plate solving is done manually with ASTAP before running
    # Galactic_3_Stretch.py which handles SPCC through final save.
    # ------------------------------------------------------------------
    siril_log(siril, "  [2/3] Saving LRGB composite...")
    if not cmd_safe(siril, "load", str(lrgb_path)):
        siril_log(siril, "  [ERROR] Cannot load LRGB.")
        return False
    if not cmd_safe(siril, "save", str(lrgb_out)):
        siril_log(siril, "  [ERROR] Cannot save LRGB.")
        return False
    siril_log(siril, "  Saved: " + lrgb_out.name)

    # ------------------------------------------------------------------
    # Step 3: Optional border crop -- removes registration/compositing
    # artifacts at the edges (see "Optional border crop" config comment).
    # Safe to do here since no WCS exists yet (ASTAP plate-solves AFTER
    # this script runs), so there's nothing to invalidate.
    # ------------------------------------------------------------------
    if RUN_CROP:
        siril_log(siril, "  [3/3] Cropping borders (mode=" + CROP_MODE + ")...")
        crop_ok, top, bottom, left, right = apply_crop(lrgb_out)
        if crop_ok:
            siril_log(siril, "  Cropped margins (top,bottom,left,right): "
                      + "{}, {}, {}, {} px".format(top, bottom, left, right))
            # Reload the cropped file so what's displayed/loaded in Siril
            # matches the actual saved output, rather than leaving the
            # uncropped composite showing.
            if not cmd_safe(siril, "load", str(lrgb_out)):
                siril_log(siril, "  [WARNING] Cropped, but could not reload into Siril for display.")
        else:
            siril_log(siril, "  [WARNING] Crop failed or margins too large -- composite left uncropped.")
    else:
        siril_log(siril, "  [3/3] Border crop skipped (RUN_CROP = False).")

    siril_log(siril, "  --> Plate-solve with ASTAP" + ("" if RUN_CROP else ", crop borders,")
              + " then run Galactic_3_Stretch.py")
    siril_log(siril, "  Panel " + prefix + " complete.")
    return True


def main():
    siril = s.SirilInterface()

    try:
        siril.connect()
        siril_log(siril, "AlpacaPano-LRGB v1.0.1 connected.")
    except Exception as exc:
        print("AlpacaPano-LRGB: could not connect to Siril: " + str(exc))
        return

    try:
        siril.cmd("requires", "1.4.0")
    except Exception:
        siril.error_messagebox(
            "AlpacaPano-LRGB requires Siril 1.4.0 or later. Please update Siril."
        )
        siril.disconnect()
        return

    try:
        home_dir = Path(siril.get_siril_wd())
        siril_log(siril, "Home directory: " + str(home_dir))

        # Verify channel directories exist
        # Auto-detect or use configured composite mode
        mode = detect_composite_mode(home_dir)
        if mode is None:
            siril_log(siril, "[ERROR] Could not detect composite mode.")
            siril_log(siril, "  LRGB needs: L/R/G/B stacked dirs with stack_denoised files.")
            siril_log(siril, "  HSO/SHO needs: Ha/Sii/Oiii stacked dirs.")
            siril_log(siril, "  Or set COMPOSITE_MODE explicitly in the config section.")
            siril.disconnect()
            return

        channel_dirs = {
            "LRGB": CHANNEL_DIRS_LRGB,
            "HSO":  CHANNEL_DIRS_HSO,
            "SHO":  CHANNEL_DIRS_SHO,
        }[mode]
        siril_log(siril, "Composite mode: " + mode)
        siril_log(siril, "Channel mapping:")
        for ch, rel in channel_dirs.items():
            siril_log(siril, "  " + ch + " <- " + rel)

        # Find panels with all required channels present
        panels = find_panel_files(home_dir, mode, channel_dirs)

        if not panels:
            siril_log(siril, "No complete " + mode + " panels found.")
            siril_log(siril, "Expected stack_denoised files in: "
                      + ", ".join(channel_dirs.values()))
            siril.disconnect()
            return

        siril_log(siril, "Found " + str(len(panels)) + " complete " + mode + " panel(s):")
        for prefix in panels:
            siril_log(siril, "  " + prefix)

        ok = fail = skip = 0
        results = []
        for prefix, files in panels.items():
            # Check skip before calling -- lrgb_out path
            composite_suffix = {
                "LRGB": "_LRGB", "HSO": "_HSO", "SHO": "_SHO"
            }[mode]
            composites_dir = home_dir / "composites"
            already = any(
                (composites_dir / (prefix + composite_suffix + ext)).exists()
                for ext in (".fits", ".fit", ".fts")
            )
            if already:
                siril_log(siril, "SKIP: " + prefix + composite_suffix + " already exists.")
                skip += 1
                results.append((prefix, "SKIP"))
            elif process_panel(siril, prefix, files, home_dir, mode):
                ok += 1
                results.append((prefix, "OK"))
            else:
                fail += 1
                results.append((prefix, "FAIL"))

        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "Galactic_2_Composite complete.")
        siril_log(siril, "=" * 60)
        siril_log(siril, "  {:<20} {:>6}".format("Panel", "Result"))
        siril_log(siril, "  " + "-" * 28)
        for prefix, status in results:
            siril_log(siril, "  {:<20} {:>6}".format(prefix, status))
        siril_log(siril, " ")
        siril_log(siril, "  OK  : " + str(ok)
                  + "   SKIP: " + str(skip)
                  + "   FAIL: " + str(fail)
                  + "   TOTAL: " + str(len(results)))
        siril_log(siril, "  Next: plate-solve composites/GLAT*_LRGB.fits with ASTAP,")
        siril_log(siril, "        crop borders, then run Galactic_3_Stretch.py")
        siril_log(siril, "=" * 60)

        cmd_safe(siril, "cd", str(home_dir))

    except Exception as exc:
        siril_log(siril, "Unhandled error: " + str(exc))
        traceback.print_exc()

    finally:
        # Always return to home directory on exit or interrupt
        try:
            home_dir = Path(siril.get_siril_wd())
            siril.cmd("cd", _quote_if_needed(str(home_dir)))
        except Exception:
            pass
        siril.disconnect()


# Siril runs scripts via exec() so __name__ != '__main__' -- call directly
main()