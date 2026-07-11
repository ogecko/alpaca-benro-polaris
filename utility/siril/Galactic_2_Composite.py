# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_2_Composite.py
# Version: 2.1.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# ==============================================================================
# OVERVIEW
# ==============================================================================
# Combines each panel's stacked channels into a single composite image.
# Composite mode is auto-detected from the stacked directories present:
#
#   LRGB : L/R/G/B stacked dirs -> luminance + colour composition
#   SHO  : Ha/Sii/Oiii stacked dirs -> Hubble palette (SII=R, Ha=G, OIII=B)
#   HSO  : as SHO but Ha=R, SII=G, OIII=B (set COMPOSITE_MODE manually)
#
# For each panel where every required channel is present:
#
#   1. Align every channel together in one sequence, then crop to their
#      common overlap                                (RUN_CROP handles any
#                                                       residual border after)
#   2. Compose with rgbcomp
#   3. Save GLATnnnX_GLONnnn_(LRGB|SHO|HSO)[_NNNs].fits to composites/
#   4. Crop any remaining border artifacts            (optional, RUN_CROP)
#
# Note: an OSC panel's stack is already a complete colour image and doesn't
# need this script -- feed it directly into Galactic_3_Stretch.py instead.
#
# After this script, before running Galactic_3_Stretch.py:
#   Batch plate-solve composites/GLAT*_(LRGB|HSO|SHO)*.fits with ASTAP
#   (File -> Batch plate-solve). This writes the WCS needed for SPCC.
#
# Prerequisites
# -------------
#   Siril 1.4.0 or later.
#   ASTAP installed with a star database (D50 recommended).
#   Run Galactic_1_Stack.py first.

import sirilpy as s
import traceback
from pathlib import Path
from collections import defaultdict

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# ------------------------------------------------------------------------
# Step 0: Composite mode selection
# ------------------------------------------------------------------------
# Set to None to auto-detect from available stacked directories, or force a
# specific mode. "HSO" always needs to be set manually since its stacked
# directories are the same as "SHO" -- only the R/B mapping differs.
COMPOSITE_MODE = None   # None = auto-detect, or "LRGB" / "HSO" / "SHO"

# Channel directories per composite mode (relative to Siril home directory).
# Keys match what rgbcomp expects: L (luminance) + R/G/B for LRGB, or R/G/B
# (mapped from the narrowband filters) for SHO/HSO.
CHANNEL_DIRS_LRGB = {
    "L": "L/stacked",
    "R": "R/stacked",
    "G": "G/stacked",
    "B": "B/stacked",
}
CHANNEL_DIRS_SHO = {          # Hubble palette: SII->R, Ha->G, OIII->B
    "R": "Sii/stacked",
    "G": "Ha/stacked",
    "B": "Oiii/stacked",
}
CHANNEL_DIRS_HSO = {          # Alternative: Ha->R, SII->G, OIII->B
    "R": "Ha/stacked",
    "G": "Sii/stacked",
    "B": "Oiii/stacked",
}

# ------------------------------------------------------------------------
# Directory layout / file matching (used throughout)
# ------------------------------------------------------------------------
INPUT_SUFFIX    = "_stack"                    # e.g. GLAT007N_GLON344_stack.fits
FITS_EXTENSIONS = (".fits", ".fit", ".fts")
PREFIX_LENGTH   = 16                          # panel prefix length, e.g. "GLAT007N_GLON344"

SUFFIX_BY_MODE = {             # output suffix per mode, written into composites/
    "LRGB": "_LRGB",
    "HSO":  "_HSO",
    "SHO":  "_SHO",
}

# ------------------------------------------------------------------------
# Step 4: Border crop -- RUN_CROP
# ------------------------------------------------------------------------
# The channel alignment step already crops to the common overlap across all
# channels, so this is a secondary safety net for anything that slips
# through (e.g. minor per-channel PSF/colour differences right at the edge).
# Safe to run before ASTAP plate-solving -- there's no WCS yet to invalidate.
RUN_CROP  = True
CROP_MODE = "auto"    # "fixed" | "auto" | "auto_or_fixed_min"
                       #   fixed: always crop CROP_FIXED_PERCENT from every edge
                       #   auto: detect the artifact border per edge automatically
                       #   auto_or_fixed_min: auto-detect, floored at CROP_FIXED_PERCENT
CROP_FIXED_PERCENT = 2.5   # percent cropped from each edge in "fixed" mode,
                           # or the floor in "auto_or_fixed_min"

# Auto-detection: a pixel counts as an artifact if any channel is at/near
# exactly 0 there (real background noise in linear data is never exactly
# 0.0). Scans inward from each edge; an edge is considered clean once
# CROP_AUTO_CONSECUTIVE_GOOD rows/columns in a row fall below
# CROP_AUTO_INVALID_FRAC.
CROP_AUTO_INVALID_FRAC     = 0.02    # fraction of a row/column allowed to be
                                     # zero-in-any-channel and still count as clean
CROP_AUTO_CONSECUTIVE_GOOD = 5       # consecutive clean rows/columns needed
CROP_AUTO_MAX_PERCENT      = 10.0    # safety cap on auto-detected crop, per edge

# ------------------------------------------------------------------------
# Debug
# ------------------------------------------------------------------------
DEBUG_KEEP_TEMP = False   # keep _lrgb_align_* temp directories for inspection
# ==============================================================================


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


def _parse_exposure_seconds(stem):
    """
    If stem ends with an exposure postfix (e.g. "..._300s", as written by
    Galactic_1_Stack.py), return the integer seconds. Otherwise None.
    """
    import re
    m = re.search(r'_(\d+)s$', stem)
    if m:
        return int(m.group(1))
    return None


def sum_exposure_across_channels(files):
    """
    Sum the exposure postfix parsed from each channel's stacked filename.
    Returns (total_seconds, any_missing) -- any_missing is True if any
    channel's file had no parseable exposure postfix (e.g. it was stacked
    before RUN_EXPOSURE_POSTFIX existed), in which case the composite's
    own postfix should be omitted rather than showing an undercounted
    total.
    """
    total = 0
    any_missing = False
    for f in files.values():
        secs = _parse_exposure_seconds(f.stem)
        if secs is None:
            any_missing = True
        else:
            total += secs
    return total, any_missing


def exposure_postfix(total_seconds, any_missing):
    """Format "_1200s", or "" if the total is unknown/zero."""
    if any_missing or total_seconds <= 0:
        return ""
    return "_{}s".format(int(total_seconds))


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
    total_exp, exp_missing = sum_exposure_across_channels(files)
    exp_suffix = exposure_postfix(total_exp, exp_missing)
    if exp_suffix:
        siril_log(siril, "  Total exposure (summed across channels): " + str(total_exp) + "s")
    lrgb_out = composites_dir / (prefix + composite_suffix + exp_suffix + ".fits")

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
    # rgbcomp has no built-in alignment -- it's purely a pixel combiner. All
    # channels are registered together in one sequence (reference first),
    # then cropped to their common overlap with seqapplyreg -framing=min, so
    # every channel is the same size before rgbcomp combines them.
    #
    # A temporary work directory avoids polluting the home dir with sequence
    # files, cleaned up afterwards.
    # ------------------------------------------------------------------
    siril_log(siril, "  [1/3] Aligning channels then LRGB composition...")

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

    # Determine reference and colour channels from mode
    if mode == "LRGB":
        # L is the luminance reference; R/G/B are colour channels
        ref_ch = "L"
        colour_channels = ["R", "G", "B"]
    else:
        # Narrowband: use G as the reference (Ha in SHO, Sii in HSO).
        ref_ch = "G"
        colour_channels = ["R", "B"]

    all_channels = [ref_ch] + colour_channels   # frame order in the sequence

    src_ext = files[ref_ch].suffix
    ext_no_dot = src_ext.lstrip(".")
    cmd_safe(siril, "setext", ext_no_dot)

    # Build one sequence containing every channel (reference first):
    #   <seq>_00001.<ext> = reference (L, or G for narrowband)
    #   <seq>_00002.<ext>, 00003, 00004 = the other channels, in order
    seq_name = "".join(all_channels)   # e.g. "LRGB" or "GRB"

    for i, ch_name in enumerate(all_channels, start=1):
        ch_copy = align_dir / ("{}_{:05d}{}".format(seq_name, i, src_ext))
        try:
            _shutil.copy2(files[ch_name], ch_copy)
        except Exception as exc:
            siril_log(siril, "  [ERROR] Could not copy " + ch_name + " channel: " + str(exc))
            if not DEBUG_KEEP_TEMP:
                _shutil.rmtree(align_dir, ignore_errors=True)
            cmd_safe(siril, "cd", str(home_dir))
            return False

    siril_log(siril, "  Registering " + "+".join(colour_channels)
              + " against " + ref_ch + " (seq=" + seq_name + ")...")
    # NOTE: -2pass runs its own quality-based reference selection, which may
    # override this setref -- Siril's docs don't specify which takes
    # precedence, but -2pass's choice should be at least as good.
    cmd_safe(siril, "setref", seq_name, "1")   # frame 1 = reference channel

    reg_ok = cmd_safe(siril, "register", seq_name, "-2pass", "-transf=homography")
    if reg_ok:
        reg_ok = cmd_safe(siril, "seqapplyreg", seq_name, "-framing=min")
    if not reg_ok:
        # Homography failed (poor seeing, elongated stars, few matches).
        # Fall back through progressively simpler transforms, for the
        # whole sequence (all channels registered together, so the
        # fallback applies to all of them together too).
        for fallback in ("affine", "similarity", "shift"):
            siril_log(siril, "  Retrying with -transf=" + fallback + "...")
            reg_ok = cmd_safe(siril, "register", seq_name, "-2pass", "-transf=" + fallback)
            if reg_ok:
                reg_ok = cmd_safe(siril, "seqapplyreg", seq_name, "-framing=min")
            if reg_ok:
                siril_log(siril, "  Registered with fallback -transf=" + fallback)
                break
    if not reg_ok:
        siril_log(siril, "  [ERROR] Registration failed -- all transforms tried.")
        if not DEBUG_KEEP_TEMP:
            _shutil.rmtree(align_dir, ignore_errors=True)
        cmd_safe(siril, "cd", str(home_dir))
        return False

    # Read back the registered+cropped frame for each channel by its
    # position in the sequence.
    reg_path = {}
    for i, ch_name in enumerate(all_channels, start=1):
        r_path = None
        for ext in FITS_EXTENSIONS:
            candidate = align_dir / ("r_{}_{:05d}{}".format(seq_name, i, ext))
            if candidate.exists():
                r_path = candidate
                break
        if r_path is None:
            siril_log(siril, "  [ERROR] Registered " + ch_name + " output not found.")
            if not DEBUG_KEEP_TEMP:
                _shutil.rmtree(align_dir, ignore_errors=True)
            cmd_safe(siril, "cd", str(home_dir))
            return False
        reg_path[ch_name] = r_path
        siril_log(siril, "  Registered: " + ch_name + " -> " + r_path.name)

    r_ref = reg_path[ref_ch]
    reg_colour = {ch: reg_path[ch] for ch in colour_channels}
    siril_log(siril, "  All channels aligned and cropped to common overlap.")

    # SPCC (run in Galactic_3_Stretch.py) handles colour balance via stellar
    # photometry, so the aligned channels are passed to rgbcomp unmodified.
    siril_log(siril, "  Channels aligned -- proceeding to rgbcomp.")

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

    # Clean up the intermediate rgbcomp output (named without the exposure
    # postfix) now that the final, exposure-suffixed file has been saved
    # successfully -- otherwise both versions of the same composite sit
    # side by side in composites/ indefinitely. Guard against the case
    # where they're actually the same file (e.g. exposure was unknown, so
    # lrgb_out has no postfix either) so we don't delete what we just saved.
    if lrgb_path.resolve() != lrgb_out.resolve():
        try:
            lrgb_path.unlink()
            siril_log(siril, "  Removed intermediate: " + lrgb_path.name)
        except OSError as exc:
            siril_log(siril, "  [WARNING] Could not remove intermediate "
                      + lrgb_path.name + ": " + str(exc))

    # ------------------------------------------------------------------
    # Step 3: Optional supplementary border crop -- see RUN_CROP config.
    # Safe here since no WCS exists yet (ASTAP plate-solves after this
    # script runs), so there's nothing to invalidate.
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
            # Check skip before calling -- lrgb_out path. Exposure postfix
            # has to be computed first (same reasoning as Galactic_1_Stack.py):
            # the expected filename depends on it, so the skip-check has to
            # know it before it can look for the right file.
            composite_suffix = {
                "LRGB": "_LRGB", "HSO": "_HSO", "SHO": "_SHO"
            }[mode]
            total_exp, exp_missing = sum_exposure_across_channels(files)
            exp_suffix = exposure_postfix(total_exp, exp_missing)
            composites_dir = home_dir / "composites"
            already = any(
                (composites_dir / (prefix + composite_suffix + exp_suffix + ext)).exists()
                for ext in (".fits", ".fit", ".fts")
            )
            if already:
                siril_log(siril, "SKIP: " + prefix + composite_suffix + exp_suffix + " already exists.")
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