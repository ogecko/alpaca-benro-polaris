# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_2_Recompose.py
# Version: 2.0.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# Description
# -----------
# Scans the Siril home directory for subdirectories L/stacked, R/stacked,
# G/stacked and B/stacked.  For every GLAT/GLON prefix where all four
# channels have a matching _stack_denoised.fits file, this script:
#
#   1.  Align channels -- register R, G, B against L (homography with fallbacks)
#   2.  LRGB Compose  -- rgbcomp
#   3.  Save GLATnnnX_GLONnnn_LRGB.fits into the process/ subdirectory
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
# Output files (all in <home>/process/):
#   GLATnnnX_GLONnnn_LRGB.fits    (linear composite, ready for ASTAP + crop)

import sirilpy as s
import traceback
from pathlib import Path
from collections import defaultdict

# ---------------------------------------------------------------------------
# CONFIGURATION -- edit these values as needed
# ---------------------------------------------------------------------------

# Subdirectory names to search (relative to Siril home directory)
CHANNEL_DIRS = {
    "L": "L/stacked",
    "R": "R/stacked",
    "G": "G/stacked",
    "B": "B/stacked",
}

# Input file suffix to look for in each channel directory
INPUT_SUFFIX = "_stack_denoised"      # e.g. GLAT007N_GLON344_stack_denoised.fits
FITS_EXTENSIONS = (".fits", ".fit", ".fts")

# First N characters of filename used as the panel prefix key
PREFIX_LENGTH = 16   # e.g. "GLAT007N_GLON344"

# Output suffix -- LRGB composite written into process/ subdir
SUFFIX_LRGB = "_LRGB"

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
    Scan L/stacked, R/stacked, G/stacked, B/stacked for stack_denoised files.

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

    # Intermediate files go into process/ -- home/ stays clean
    process_dir = home_dir / "process"
    process_dir.mkdir(exist_ok=True)

    lrgb_out = process_dir / (prefix + SUFFIX_LRGB + ".fits")

    # Skip if LRGB composite already exists in process/
    # (Galactic_3 skip is separate -- it checks for _stretched_result in home/)
    if lrgb_out.exists():
        siril_log(siril, "  SKIP: LRGB already composed: " + lrgb_out.name)
        siril_log(siril, "  (Delete from process/ to recompose)")
        return True

    # No stale cleanup -- process/ keeps intermediates for diagnosis

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

    # L is used as-is (it is the reference; no transform needed)
    r_L = l_copy
    r_R = reg_colour["R"]
    r_G = reg_colour["G"]
    r_B = reg_colour["B"]
    siril_log(siril, "  All channels aligned:")
    siril_log(siril, "    L=" + r_L.name + "  R=" + r_R.name
              + "  G=" + r_G.name + "  B=" + r_B.name)

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

    # L scaling removed -- CIE Lab (-cfa flag on rgbcomp) handles
    # luminance/colour separation correctly without needing pre-scaling.
    # Scaling L to match RGB median was causing issues when L happened
    # to be dimmer than RGB (scale > 1.0), making the gamut problem worse.
    scaled_L = r_L

    # Compose LRGB from aligned + scaled channels; write result to process_dir
    cmd_safe(siril, "cd", str(process_dir))
    lrgb_stem = prefix + SUFFIX_LRGB
    # -cfa uses CIE Lab colour space for LRGB composition.
    # Lab has a much larger gamut than HSL/HSV -- orange stars stay
    # orange even when L is brighter than the colour channels, because
    # Lab separates luminance from chrominance completely.
    if not cmd_safe(
        siril,
        "rgbcomp",
        "-lum=" + str(scaled_L),
        str(r_R),
        str(r_G),
        str(r_B),
        "-cfa",
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
        candidate = process_dir / (lrgb_stem + ext)
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
    siril_log(siril, "  [2/2] Saving LRGB composite...")
    if not cmd_safe(siril, "load", str(lrgb_path)):
        siril_log(siril, "  [ERROR] Cannot load LRGB.")
        return False
    if not cmd_safe(siril, "save", str(lrgb_out)):
        siril_log(siril, "  [ERROR] Cannot save LRGB.")
        return False
    siril_log(siril, "  Saved: " + lrgb_out.name)
    siril_log(siril, "  --> Plate-solve with ASTAP then run Galactic_3_Stretch.py")
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
            siril_log(siril, "in subdirectories: L/stacked, R/stacked, G/stacked, B/process")
            siril.disconnect()
            return

        siril_log(siril, "Found " + str(len(panels)) + " complete LRGB panel(s):")
        for prefix in panels:
            siril_log(siril, "  " + prefix)

        ok = fail = skip = 0
        results = []
        for prefix, files in panels.items():
            if process_panel(siril, prefix, files, home_dir):
                # Check if it was a skip (LRGB already existed)
                process_dir = home_dir / "process"
                existed_before = any(
                    (process_dir / (prefix + "_LRGB" + ext)).exists()
                    for ext in (".fits", ".fit", ".fts"))
                # process_panel returns True for both OK and SKIP
                # We detect skip by checking the log message was printed
                # Simpler: just count OK for now, skip logic is in process_panel
                ok += 1
                results.append((prefix, "OK"))
            else:
                fail += 1
                results.append((prefix, "FAIL"))

        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "Galactic_2_Recompose complete.")
        siril_log(siril, "=" * 60)
        siril_log(siril, "  {:<20} {:>6}".format("Panel", "Result"))
        siril_log(siril, "  " + "-" * 28)
        for prefix, status in results:
            siril_log(siril, "  {:<20} {:>6}".format(prefix, status))
        siril_log(siril, " ")
        siril_log(siril, "  OK  : " + str(ok)
                  + "   FAIL: " + str(fail)
                  + "   TOTAL: " + str(len(results)))
        siril_log(siril, "  Next: plate-solve process/GLAT*_LRGB.fits with ASTAP")
        siril_log(siril, "        then run Galactic_3_Stretch.py")
        siril_log(siril, "=" * 60)

    except Exception as exc:
        siril_log(siril, "Unhandled error: " + str(exc))
        traceback.print_exc()

    finally:
        siril.disconnect()


# Siril runs scripts via exec() so __name__ != '__main__' -- call directly
main()