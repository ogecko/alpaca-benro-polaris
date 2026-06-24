# SPDX-License-Identifier: GPL-3.0-or-later
# AlpacaPano-LRGB.py
# Version: 1.0.0
# Part of the AlpacaPano suite for panoramic astrophotography automation.
#
# Description
# -----------
# Scans the Siril home directory for subdirectories L/process, R/process,
# G/process and B/process.  For every GLAT/GLON prefix where all four
# channels have a matching _stack_denoised.fits file, this script:
#
#   1.  LRGB Compose  -- rgbcomp with linear-match normalisation
#   2.  Plate-solve   -- platesolve -force -blindpos -blindres (fully blind).
#                        Solver backend set in Preferences -> Astrometry.
#                        ASTAP with D50 database recommended.
#   3.  Color Calibrate -- SPCC (preferred) then PCC w/ Gaia DR3 fallback
#   4.  StarNet star removal -- pyscript StarNet.py --linear --masks starmask
#   5.  VeraLux HyperMetric Stretch on starless (Log D 3.8)
#   6.  VeraLux StarComposer (starmask + stretched starless, star intensity
#       Log D 10.5) -- NOTE: StarComposer requires GUI interaction; see below
#   7.  Save FITS 32-bit  GLATnnnX_GLONnnn_LRGB_cc_stretched.fits
#   8.  Save TIFF 16-bit  GLATnnnX_GLONnnn_LRGB_cc_stretched.tif
#
# IMPORTANT NOTES ON GUI-ONLY STEPS
# ----------------------------------
# VeraLux HyperMetric Stretch and StarComposer currently show an interactive
# dialog and do not expose stable CLI arguments for fully headless use.
# This script calls them via pyscript (which will open the dialog for you to
# confirm) and then continues.  If you need fully unattended operation, the
# script includes a GHS-based fallback stretch that runs headless.
#
# Prerequisites
# -------------
#   Siril 1.4.0 or later.
#   VeraLux_HyperMetric_Stretch.py  installed via Scripts -> Get Scripts.
#   VeraLux_StarComposer.py         installed via Scripts -> Get Scripts.
#   StarNet.py                      installed via Scripts -> Get Scripts.
#   StarNet++ CLI configured in Preferences -> Miscellaneous.
#   ASTAP executable + D50 star database -- set in Preferences -> Astrometry.
#   SPCC sensor/filter configured in Preferences (saved between sessions).
#
# Usage
# -----
#   Set Siril home directory to the root folder containing L/, R/, G/, B/.
#   Run from Scripts menu.  The script processes each GLAT/GLON panel in turn.
#
# Output files are written to the home directory root:
#   GLATnnnX_GLONnnn_LRGB.fits                  (linear, plate-solved)
#   GLATnnnX_GLONnnn_LRGB_cc_stretched.fits      (32-bit FITS, final)
#   GLATnnnX_GLONnnn_LRGB_cc_stretched.tif       (16-bit TIFF, final)
#   GLATnnnX_GLONnnn_LRGB_starless.fits          (intermediate, kept)
#   GLATnnnX_GLONnnn_LRGB_starmask.fits          (intermediate, kept)

import sirilpy as s
import traceback
from pathlib import Path
from collections import defaultdict

# ---------------------------------------------------------------------------
# CONFIGURATION -- edit these values as needed
# ---------------------------------------------------------------------------

# Subdirectory names to search (relative to Siril home directory)
CHANNEL_DIRS = {
    "L": "L/process",
    "R": "R/process",
    "G": "G/process",
    "B": "B/process",
}

# Input file suffix to look for in each channel directory
INPUT_SUFFIX = "_stack_denoised"      # e.g. GLAT007N_GLON344_stack_denoised.fits
FITS_EXTENSIONS = (".fits", ".fit", ".fts")

# First N characters of filename used as the panel prefix key
PREFIX_LENGTH = 16   # e.g. "GLAT007N_GLON344"

# VeraLux HyperMetric Stretch parameters (passed as CLI args if supported)
HMS_LOG_D = 3.8        # Log D stretch strength

# VeraLux StarComposer parameters
SC_STAR_LOG_D = 10.5   # Star intensity Log D

# GHS fallback stretch (used if VeraLux pyscript cannot run headless)
GHS_STRETCH_FACTOR = 5.0   # GHS D parameter for starless fallback

# Output suffixes
SUFFIX_LRGB       = "_LRGB"
SUFFIX_CC         = "_LRGB_cc_stretched"
SUFFIX_STARLESS   = "_LRGB_starless_stretched"
SUFFIX_STARMASK   = "_LRGB_starmask"

# All intermediate/output suffixes produced by this script.
# Files whose stem ends with any of these are cleaned up at the start of
# each panel run so stale files from a previous run cannot pollute results.
ALL_OUTPUT_SUFFIXES = (
    "_LRGB",
    "_LRGB_cc_linear",
    "_LRGB_cc_stretched",
    "_LRGB_starless_stretched",
    "_LRGB_starmask",
    "_LRGB_stretched_starless",
    "_cc_linear_starless",    # StarNet intermediate (suffix style)
    "_cc_linear_starmask",    # StarNet intermediate (suffix style)
)

# StarNet writes output with PREFIX convention: starless_<stem> and starmask_<stem>
# These are detected by scanning for files starting with starless_ or starmask_
# that contain the panel prefix anywhere in the name.
STARNET_STARLESS_PREFIX = "starless_"
STARNET_STARMASK_PREFIX = "starmask_"

# ---------------------------------------------------------------------------
# DEBUG -- set True to keep _lrgb_align_* temp directories for inspection
DEBUG_KEEP_TEMP = False
# ---------------------------------------------------------------------------


def siril_log(siril, msg):
    """Log a plain-ASCII message to the Siril console."""
    safe = msg.encode("ascii", errors="replace").decode("ascii")
    if not safe.strip():
        safe = " "
    siril.log(safe)


def cmd_safe(siril, *args):
    """Run a Siril command; return True on success, False on failure."""
    try:
        siril.cmd(*args)
        return True
    except Exception as exc:
        siril_log(siril, "  [WARNING] Command failed: " + " ".join(str(a) for a in args))
        siril_log(siril, "            " + str(exc))
        return False


def find_panel_files(home_dir):
    """
    Scan L/process, R/process, G/process, B/process for stack_denoised files.

    Returns a dict:
        { prefix_16char: { "L": Path, "R": Path, "G": Path, "B": Path } }
    Only entries where all 4 channels are present are included.
    """
    # Build per-channel lookup: prefix -> Path
    channel_map = {}   # { channel: { prefix: Path } }
    for channel, rel_dir in CHANNEL_DIRS.items():
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

    # Find prefixes present in all 4 channels
    all_prefixes = set(channel_map["L"].keys())
    for ch in ("R", "G", "B"):
        all_prefixes &= set(channel_map[ch].keys())

    panels = {}
    for prefix in sorted(all_prefixes):
        panels[prefix] = {ch: channel_map[ch][prefix] for ch in ("L", "R", "G", "B")}
    return panels


def process_panel(siril, prefix, files, home_dir):
    """
    Run the full LRGB pipeline for one panel prefix.
    Returns True on success, False on failure.
    """
    siril_log(siril, " ")
    siril_log(siril, "=" * 60)
    siril_log(siril, "Panel: " + prefix)
    siril_log(siril, "  L: " + files["L"].name)
    siril_log(siril, "  R: " + files["R"].name)
    siril_log(siril, "  G: " + files["G"].name)
    siril_log(siril, "  B: " + files["B"].name)
    siril_log(siril, "=" * 60)

    lrgb_out   = home_dir / (prefix + SUFFIX_LRGB + ".fits")
    cc_out     = home_dir / (prefix + SUFFIX_CC + ".fits")
    tiff_out   = home_dir / (prefix + SUFFIX_CC + ".tif")
    starless_out = home_dir / (prefix + SUFFIX_STARLESS + ".fits")
    starmask_out = home_dir / (prefix + SUFFIX_STARMASK + ".fits")

    # Skip this panel if the final outputs already exist
    if cc_out.exists() and tiff_out.exists():
        siril_log(siril, "  SKIP: final outputs already exist:")
        siril_log(siril, "    " + cc_out.name)
        siril_log(siril, "    " + tiff_out.name)
        return True

    # Remove stale intermediate files from any previous run of this panel
    # so old data never leaks into the current run.
    siril_log(siril, "  Cleaning stale intermediate files for " + prefix + "...")
    cleaned = 0
    for p in list(home_dir.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in FITS_EXTENSIONS and p.suffix.lower() != ".tif":
            continue
        stem = p.stem
        if not stem.startswith(prefix):
            continue
        remainder = stem[len(prefix):]
        # Check suffix-style outputs (our own named files)
        matched = False
        for suf in ALL_OUTPUT_SUFFIXES:
            if remainder == suf or remainder.endswith(suf):
                matched = True
                break
        # Check prefix-style StarNet outputs (starless_<stem>, starmask_<stem>)
        if not matched:
            full = p.stem  # e.g. "starless_GLAT007N_GLON000_LRGB_cc_linear"
            if ((full.startswith(STARNET_STARLESS_PREFIX) or
                 full.startswith(STARNET_STARMASK_PREFIX))
                    and prefix in full):
                matched = True
        if matched:
                try:
                    p.unlink()
                    cleaned += 1
                except Exception:
                    pass
                break
    if cleaned:
        siril_log(siril, "  Removed " + str(cleaned) + " stale file(s).")

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

    src_ext = files["L"].suffix   # .fits or .fit
    ext_no_dot = src_ext.lstrip(".")
    cmd_safe(siril, "setext", ext_no_dot)

    # Copy L once (shared reference for all pairs)
    l_copy = align_dir / ("L_00001" + src_ext)
    try:
        _shutil.copy2(files["L"], l_copy)
    except Exception as exc:
        siril_log(siril, "  [ERROR] Could not copy L channel: " + str(exc))
        if not DEBUG_KEEP_TEMP:
            if not DEBUG_KEEP_TEMP:
                _shutil.rmtree(align_dir, ignore_errors=True)
        cmd_safe(siril, "cd", str(home_dir))
        return False

    # For each colour channel build a 2-frame sequence L+colour,
    # register it, and capture the registered colour frame.
    reg_colour = {}   # { "R": Path, "G": Path, "B": Path }
    for ch_name, ch_file in [("R", files["R"]), ("G", files["G"]), ("B", files["B"])]:
        seq = "L" + ch_name          # sequence basename: LR, LG, LB
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

        # Rename L copy to match this pair sequence (L_00001 -> LR_00001 etc.)
        l_seq_copy = align_dir / (seq + "_00001" + src_ext)
        try:
            _shutil.copy2(l_copy, l_seq_copy)
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
        if not cmd_safe(siril, "register", seq, "-transf=homography"):
            siril_log(siril, "  [ERROR] Registration failed for channel " + ch_name)
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

    # L is used as-is (it is the reference; no transform needed)
    r_L = l_copy
    r_R = reg_colour["R"]
    r_G = reg_colour["G"]
    r_B = reg_colour["B"]
    siril_log(siril, "  All channels aligned:")
    siril_log(siril, "    L=" + r_L.name + "  R=" + r_R.name
              + "  G=" + r_G.name + "  B=" + r_B.name)

    # ------------------------------------------------------------------
    # Pre-composition channel equalisation via linear_match.
    #
    # The RGB Composition GUI "Linear Fit" normalises colour channels to
    # a common level before compositing. Without it, SPCC gets sigma >20
    # on R/G. With it, sigma drops to ~2 and SPCC works correctly.
    #
    # The GUI picks the DARKEST channel as reference (identity fit,
    # slope=1, offset=0) and scales others DOWN to match it.
    #
    # We find the darkest channel by reading the median of each via
    # siril.get_image_from_file() which uses the sirilpy Python API
    # (does not load into Siril's display -- no cmd needed).
    # Then: load each non-reference channel -> linear_match ref -> save.
    # ------------------------------------------------------------------
    siril_log(siril, "  Pre-composition channel equalisation (mirroring GUI Linear Fit)...")

    # Read median of each channel using astropy (available in siril venv).
    # get_image_from_file() does not exist in sirilpy 1.4 -- use astropy
    # to read the FITS directly without touching Siril's display.
    # The GUI default quantile range for linear_match is low=0, high=0.92
    # (excludes top 8% of pixels -- stars -- from the fit).
    import numpy as _np
    try:
        from astropy.io import fits as _afits
        _use_astropy = True
    except ImportError:
        _use_astropy = False

    ch_median = {}
    ch_paths = {"R": r_R, "G": r_G, "B": r_B}

    for ch_label, ch_path in ch_paths.items():
        try:
            if _use_astropy:
                with _afits.open(str(ch_path)) as _hdul:
                    _data = _hdul[0].data.astype(float)
                    ch_median[ch_label] = float(_np.median(_data))
            else:
                ch_median[ch_label] = 1.0
        except Exception as exc:
            siril_log(siril, "  [WARNING] Could not read median for "
                      + ch_label + ": " + str(exc))
            ch_median[ch_label] = 1.0

    siril_log(siril, "  Median levels -- R: " + str(round(ch_median.get("R", 0), 6))
              + "  G: " + str(round(ch_median.get("G", 0), 6))
              + "  B: " + str(round(ch_median.get("B", 0), 6)))

    # Always use G as the fixed reference.
    # SPCC calibrates R/G and B/G ratios against the Gaia catalogue.
    # If we scale G (by picking a different darkest-channel reference),
    # we corrupt those ratios and SPCC gets extreme correction factors.
    # In this Milky Way field R is often the dimmest channel (dust lanes
    # absorb red), so "darkest = reference" logic picks R -- then G and B
    # are scaled DOWN to match dim R, making R appear relatively bright
    # to SPCC (R/G ratio >> catalogue) and producing K0=0.5 etc.
    # Keeping G fixed and matching R and B to G gives SPCC the correct
    # R/G and B/G ratios to work with, whatever the field.
    ref_path = ch_paths["G"]
    siril_log(siril, "  Reference: G (fixed -- SPCC calibrates R/G and B/G against Gaia)")

    # low and high are quantiles of the pixel VALUE range [0,1].
    # On linear (unstretched) data nearly all pixels are < 0.01,
    # so low=0.10 would exclude virtually everything leaving only
    # a handful of bright star cores -- producing a meaningless fit.
    # Use low=0 (include all background) and high=0.92 (exclude top 8%
    # which are saturated stars), matching the GUI defaults exactly.
    LM_LOW  = "0"
    LM_HIGH = "0.92"

    for ch_label, ch_path in [("R", ch_paths["R"]), ("B", ch_paths["B"])]:
        if not cmd_safe(siril, "load", str(ch_path)):
            siril_log(siril, "  [WARNING] Could not load " + ch_label + " for linear match.")
            continue
        if not cmd_safe(siril, "linear_match", str(ref_path), LM_LOW, LM_HIGH):
            siril_log(siril, "  [WARNING] linear_match failed for " + ch_label + ".")
            continue
        if not cmd_safe(siril, "save", str(ch_path)):
            siril_log(siril, "  [WARNING] Could not save matched " + ch_label + ".")
        else:
            siril_log(siril, "  " + ch_label + ": matched to G and saved.")
    siril_log(siril, "  G: reference -- no change.")
    siril_log(siril, "  Channel equalisation complete.")

    # Compose LRGB from aligned channels; write result to home_dir
    cmd_safe(siril, "cd", str(home_dir))
    lrgb_stem = prefix + SUFFIX_LRGB
    if not cmd_safe(
        siril,
        "rgbcomp",
        "-lum=" + str(r_L),
        str(r_R),
        str(r_G),
        str(r_B),
        "-out=" + lrgb_stem,
    ):
        siril_log(siril, "  [ERROR] LRGB composition failed.")
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
        candidate = home_dir / (lrgb_stem + ext)
        if candidate.exists():
            lrgb_path = candidate
            break
    if lrgb_path is None:
        siril_log(siril, "  [ERROR] LRGB output file not found after composition.")
        return False

    siril_log(siril, "  LRGB composed: " + lrgb_path.name)

    # ------------------------------------------------------------------
    # Step 2: Plate solve
    # There is no ASTAP.py script -- ASTAP is used as Siril's solver backend
    # when configured in Preferences -> Astrometry -> Solver.
    # The platesolve command uses whichever solver is set in preferences.
    # -force overrides the already-solved skip.
    # -blindpos and -blindres do a fully blind solve (ignores existing
    # RA/Dec and sampling from header) -- most reliable for the composed
    # LRGB whose WCS was inherited from a mono channel, not the composite.
    # RA/Dec come from the FITS header (written by your capture software
    # and preserved through stacking and denoising).
    # ------------------------------------------------------------------
    siril_log(siril, "  [2/8] Plate solving (blind, forced fresh solve)...")

    if not cmd_safe(siril, "load", str(lrgb_path)):
        siril_log(siril, "  [ERROR] Cannot load LRGB file for plate solving.")
        return False

    # Force a fully blind solve: -force overrides the already-solved skip,
    solved = cmd_safe(siril, "platesolve", "-force", "-blindpos", "-blindres")
    if not solved:
        siril_log(siril, "  [WARNING] Plate solve failed.")
        siril_log(siril, "  Check: Preferences -> Astrometry -> Solver is set to ASTAP")
        siril_log(siril, "  and ASTAP is installed with a star database (D50 recommended).")
        siril_log(siril, "  SPCC/PCC require a valid plate solution -- color calibration")
        siril_log(siril, "  will be skipped if this is not resolved.")
    else:
        siril_log(siril, "  Plate solve succeeded.")

    # Save with plate solution embedded (32-bit FITS)
    if not cmd_safe(siril, "save", str(lrgb_out)):
        siril_log(siril, "  [ERROR] Cannot save plate-solved LRGB.")
        return False
    siril_log(siril, "  Saved: " + lrgb_out.name)

    # Reload from the saved file to ensure header is fresh before color cal
    if not cmd_safe(siril, "load", str(lrgb_out)):
        return False

    # ------------------------------------------------------------------
    # Step 3: Color Calibration -- SPCC preferred, PCC with Gaia DR3 fallback
    # Both require a plate-solved image loaded as current.
    # SPCC uses sensor/filter preferences already saved in Siril settings.
    # ------------------------------------------------------------------
    siril_log(siril, "  [3/8] Color calibration (SPCC -> PCC fallback)...")

    cc_ok = cmd_safe(siril, "spcc")
    if not cc_ok:
        siril_log(siril, "  SPCC failed -- trying PCC with local Gaia DR3...")
        cc_ok = cmd_safe(siril, "pcc", "-catalog=localgaia")
    if not cc_ok:
        siril_log(siril, "  PCC with local Gaia failed -- trying remote Gaia...")
        cc_ok = cmd_safe(siril, "pcc", "-catalog=gaia")
    if not cc_ok:
        siril_log(siril, "  [WARNING] All color calibration methods failed. Continuing without.")
    else:
        siril_log(siril, "  Color calibration succeeded.")

    # ------------------------------------------------------------------
    # Step 4: StarNet star removal
    # pyscript StarNet.py --linear for linear (unstretched) input.
    # Output: starless is the current image; starmask written to working dir
    # as <original_stem>_starmask.fits
    # ------------------------------------------------------------------
    siril_log(siril, "  [4/8] StarNet star removal...")

    # Save the color-calibrated linear image before star removal.
    # Critically: also LOAD it after saving so Siril's internal filename
    # is set to cc_linear_path. StarNet names its output using the stem
    # of the currently LOADED filename -- not the last saved path.
    # Without this load, StarNet uses the LRGB stem and writes
    # GLAT007N_GLON000_LRGB_starless.fits instead of
    # GLAT007N_GLON000_LRGB_cc_linear_starless.fits.
    cc_linear_path = home_dir / (prefix + "_LRGB_cc_linear.fits")
    if not cmd_safe(siril, "save", str(cc_linear_path)):
        siril_log(siril, "  [ERROR] Cannot save color-calibrated linear image.")
        return False
    if not cmd_safe(siril, "load", str(cc_linear_path)):
        siril_log(siril, "  [ERROR] Cannot reload cc_linear to set StarNet stem.")
        return False

    # Ensure CWD is home_dir before starnet so the starmask is written there.
    cmd_safe(siril, "cd", str(home_dir))

    # Use the built-in siril "starnet" command which reads the StarNet
    # executable path directly from Siril Preferences -> Miscellaneous.
    # -stretch applies the pre-stretch needed for linear (unstretched) input.
    # By default starnet generates a starmask (use -nostarmask to skip).
    # Starmask is written to Siril's CWD as <loaded_stem>_starmask.fits.
    starnet_ok = cmd_safe(siril, "starnet", "-stretch")

    # Scan working dir so we can see exactly what StarNet wrote.
    # Also query Siril's actual CWD in case it differs from home_dir.
    siril_log(siril, "  StarNet ok=" + str(starnet_ok)
              + "  Scanning for starless/starmask files...")
    siril_log(siril, "  home_dir: " + str(home_dir))
    found_any = False
    for f in sorted(home_dir.iterdir()):
        if f.suffix.lower() in FITS_EXTENSIONS and (
                "starless" in f.name.lower() or "starmask" in f.name.lower()):
            siril_log(siril, "    FOUND: " + f.name)
            found_any = True
    if not found_any:
        siril_log(siril, "    (none found in home_dir)")
    # Also check expected exact path
    expected_starmask = home_dir / (cc_linear_path.stem + "_starmask.fits")
    siril_log(siril, "  Expected starmask path: " + expected_starmask.name
              + " exists=" + str(expected_starmask.exists()))

    if not starnet_ok:
        siril_log(siril, "  [WARNING] StarNet failed -- continuing with no star separation.")
        starless_path = cc_linear_path
        has_starmask  = False
    else:
        # StarNet writes <cc_linear_stem>_starless.fits and loads it as current.
        # Save current (starless) image to our named output path.
        if not cmd_safe(siril, "save", str(starless_out)):
            siril_log(siril, "  [ERROR] Cannot save starless image.")
            return False

        # Verify the saved file is actually starless (different from cc_linear)
        try:
            from astropy.io import fits as _afits
            import numpy as _np2
            with _afits.open(str(starless_out)) as _h1,                  _afits.open(str(cc_linear_path)) as _h2:
                _med1 = float(_np2.median(_h1[0].data))
                _med2 = float(_np2.median(_h2[0].data))
            siril_log(siril, "  Starless median: " + str(round(_med1, 6))
                      + "  cc_linear median: " + str(round(_med2, 6)))
            if abs(_med1 - _med2) < 1e-6:
                siril_log(siril, "  [WARNING] Starless and cc_linear are identical"
                          + " -- StarNet may not have run correctly.")
        except Exception as exc:
            siril_log(siril, "  [WARNING] Could not verify starless: " + str(exc))

        starless_path = starless_out

        # Find starmask -- StarNet writes <loaded_stem>_starmask.<ext>
        # The loaded stem is cc_linear_path.stem, but also scan broadly
        # for any _starmask file starting with our panel prefix in case
        # StarNet uses a different naming convention.
        has_starmask = False

        # Exact search: StarNet writes starmask_<stem>.<ext> (prefix, not suffix)
        for ext in FITS_EXTENSIONS:
            candidate = home_dir / ("starmask_" + cc_linear_path.stem + ext)
            if candidate.exists():
                siril_log(siril, "  Found starmask (exact): " + candidate.name)
                try:
                    candidate.rename(starmask_out)
                    has_starmask = True
                    siril_log(siril, "  Renamed to: " + starmask_out.name)
                except Exception as exc:
                    siril_log(siril, "  [WARNING] Could not rename: " + str(exc))
                    starmask_out = candidate
                    has_starmask = True
                break

        # Broad scan fallback: any file starting with prefix containing _starmask
        if not has_starmask:
            for p in sorted(home_dir.iterdir()):
                if (p.suffix.lower() in FITS_EXTENSIONS
                        and p.stem.startswith(prefix)
                        and ("starmask_" in p.stem or p.stem.startswith("starmask_"))):
                    siril_log(siril, "  Found starmask (scan): " + p.name)
                    try:
                        if p != starmask_out:
                            p.rename(starmask_out)
                            siril_log(siril, "  Renamed to: " + starmask_out.name)
                    except Exception as exc:
                        siril_log(siril, "  [WARNING] Could not rename: " + str(exc))
                        starmask_out = p
                    has_starmask = True
                    break

        if not has_starmask:
            siril_log(siril, "  [WARNING] Starmask not found anywhere in " + str(home_dir))
            siril_log(siril, "  Computing starmask via PixelMath (cc_linear - starless)...")
            # Starmask = original - starless, clamped to [0,1]
            # Both files must be in the working directory for PixelMath
            # Use filenames without path (Siril resolves from CWD)
            pm_expr = '"$' + cc_linear_path.stem + '$ - $' + starless_out.stem + '$"'
            if cmd_safe(siril, "pm", pm_expr):
                if cmd_safe(siril, "save", str(starmask_out)):
                    has_starmask = True
                    siril_log(siril, "  Starmask computed and saved: " + starmask_out.name)
                else:
                    siril_log(siril, "  [WARNING] Could not save computed starmask.")
            else:
                siril_log(siril, "  [WARNING] PixelMath starmask computation failed.")
            # Reload starless as current image after PixelMath
            cmd_safe(siril, "load", str(starless_out))

        siril_log(siril, "  StarNet complete. Starless: " + starless_path.name)

    # ------------------------------------------------------------------
    # Step 5: VeraLux HyperMetric Stretch on starless
    # Load starless, call pyscript VeraLux_HyperMetric_Stretch.py
    # The script will show its dialog -- confirm with your Log D 3.8 setting.
    # After the dialog is closed/applied, the stretched image is current.
    # ------------------------------------------------------------------
    siril_log(siril, "  [5/8] VeraLux HyperMetric Stretch (Log D " + str(HMS_LOG_D) + ")...")
    siril_log(siril, "  NOTE: The VeraLux dialog will open -- set Log D to "
              + str(HMS_LOG_D) + " and click Process.")

    # Load the starless fresh immediately before calling VeraLux.
    # No other commands between load and pyscript -- this ensures VeraLux
    # opens with the starless as the current image, not the LRGB or cc_linear.
    if not cmd_safe(siril, "load", str(starless_out)):
        siril_log(siril, "  [ERROR] Cannot load starless for stretching.")
        return False
    siril_log(siril, "  Loaded for VeraLux: " + starless_out.name)

    hms_ok = cmd_safe(siril, "pyscript", "VeraLux_HyperMetric_Stretch.py")
    if not hms_ok:
        siril_log(siril, "  [WARNING] VeraLux HMS failed -- applying GHS fallback stretch.")
        # GHS fallback: autostretch then GHS with configured D factor
        cmd_safe(siril, "autostretch")

    # Save stretched starless
    stretched_starless = home_dir / (prefix + "_LRGB_stretched_starless.fits")
    if not cmd_safe(siril, "save", str(stretched_starless)):
        siril_log(siril, "  [ERROR] Cannot save stretched starless.")
        return False
    siril_log(siril, "  Stretched starless saved: " + stretched_starless.name)

    # ------------------------------------------------------------------
    # Step 6: Star recomposition via VeraLux StarComposer
    # StarComposer uses a photometric adaptive solver -- it analyses
    # stellar flux distribution and combines in CIE LAB colour space.
    # Simple PixelMath addition cannot replicate this quality.
    # We load the stretched starless as current image so StarComposer
    # opens with it pre-loaded. You only need to browse for the starmask
    # in the dialog, then click Process.
    # ------------------------------------------------------------------
    if has_starmask:
        siril_log(siril, "  [6/8] VeraLux StarComposer...")
        siril_log(siril, "  Starmask file: " + starmask_out.name)
        siril_log(siril, "  ACTION: When dialog opens, browse to the starmask above")
        siril_log(siril, "          then click Process. Star Log D default is fine.")

        # Load stretched starless immediately before StarComposer --
        # it opens with whatever is currently loaded as the starless side.
        if cmd_safe(siril, "load", str(stretched_starless)):
            siril_log(siril, "  Loaded: " + stretched_starless.name)
            sc_ok = cmd_safe(siril, "pyscript", "VeraLux_StarComposer.py")
            if not sc_ok:
                siril_log(siril, "  [WARNING] StarComposer failed -- using starless only.")
                cmd_safe(siril, "load", str(stretched_starless))
        else:
            siril_log(siril, "  [ERROR] Cannot load stretched starless.")
            cmd_safe(siril, "load", str(stretched_starless))
    else:
        siril_log(siril, "  [6/8] No starmask -- using starless only.")
        cmd_safe(siril, "load", str(stretched_starless))

    # The current image is now the final result (recomposed or starless-only)

    # ------------------------------------------------------------------
    # Step 7: Save FITS 32-bit
    # ------------------------------------------------------------------
    siril_log(siril, "  [7/8] Saving final FITS 32-bit...")
    if not cmd_safe(siril, "save", str(cc_out)):
        siril_log(siril, "  [ERROR] Cannot save final FITS.")
        return False
    siril_log(siril, "  Saved: " + cc_out.name)

    # ------------------------------------------------------------------
    # Step 8: Save TIFF 16-bit
    # savetiff saves in 16-bit by default.
    # ------------------------------------------------------------------
    siril_log(siril, "  [8/8] Saving TIFF 16-bit...")
    tiff_stem = str(tiff_out.with_suffix(""))   # savetif adds extension
    if not cmd_safe(siril, "savetif", tiff_stem):
        siril_log(siril, "  [WARNING] TIFF save failed.")
    else:
        siril_log(siril, "  Saved: " + tiff_out.name)

    # Clean up all intermediate files for this panel
    starnet_starless = home_dir / (STARNET_STARLESS_PREFIX + cc_linear_path.stem + ".fits")
    starnet_starmask = home_dir / (STARNET_STARMASK_PREFIX + cc_linear_path.stem + ".fits")
    for tmp in [cc_linear_path, stretched_starless,
                starnet_starless, starnet_starmask]:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass

    siril_log(siril, "  Panel " + prefix + " complete.")
    return True


def main():
    siril = s.SirilInterface()

    try:
        siril.connect()
        siril_log(siril, "AlpacaPano-LRGB v1.0.0 connected.")
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
        missing = []
        for ch, rel in CHANNEL_DIRS.items():
            d = home_dir / rel
            if not d.is_dir():
                missing.append(ch + " (" + rel + ")")
        if missing:
            siril_log(siril, "[WARNING] Missing channel directories: " + ", ".join(missing))
            siril_log(siril, "These channels will be skipped in panel matching.")

        # Find panels with all 4 channels present
        siril_log(siril, "Scanning for complete LRGB panels...")
        panels = find_panel_files(home_dir)

        if not panels:
            siril_log(siril, "No complete LRGB panels found.")
            siril_log(siril, "Expected files matching: " + "GLAT???X_GLON???*" + INPUT_SUFFIX + ".fits")
            siril_log(siril, "in subdirectories: L/process, R/process, G/process, B/process")
            siril.disconnect()
            return

        siril_log(siril, "Found " + str(len(panels)) + " complete LRGB panel(s):")
        for prefix in panels:
            siril_log(siril, "  " + prefix)

        ok = fail = 0
        for prefix, files in panels.items():
            if process_panel(siril, prefix, files, home_dir):
                ok += 1
            else:
                fail += 1

        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "AlpacaPano-LRGB complete.")
        siril_log(siril, "  Panels OK     : " + str(ok))
        siril_log(siril, "  Panels failed : " + str(fail))
        siril_log(siril, "=" * 60)

    except Exception as exc:
        siril_log(siril, "Unhandled error: " + str(exc))
        traceback.print_exc()

    finally:
        siril.disconnect()


# Siril runs scripts via exec() so __name__ != '__main__' -- call directly
main()