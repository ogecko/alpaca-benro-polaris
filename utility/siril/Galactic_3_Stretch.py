# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_3_Stretch.py
# Version: 1.1.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# Description
# -----------
# Processes plate-solved GLAT*_(LRGB|SHO|HSO).fits files from the process/
# subdirectory through the full stretch pipeline:
#
#   [1/6]  GraXpert background extraction (BGE on combined colour image)
#   [2/6]  GraXpert denoise (strength 0.5)
#   [3/6]  SPCC colour calibration (falls back to PCC with Gaia DR3)
#          -- auto-detects wideband (LRGB) vs narrowband (SHO/HSO)
#          -- set RUN_SPCC = False to skip (e.g. after manual Alchemy)
#   [4/6]  StarNet star removal (saves starless + starmask in process/)
#   [5/6]  VeraLux HyperMetric Stretch (dialog -- set Log D 3.8)
#          VeraLux StarComposer (dialog -- select both files shown in log)
#   [6/6]  Save 32-bit FITS -> result_fits/GLAT*_stretched_result.fits
#
# TIFF export is handled separately by Galactic_4_Tiff.py, allowing
# final manual adjustments to the FITS before stitching.
#
# Prerequisites
# -------------
#   - Run Galactic_2_Composite.py first to produce process/GLAT*_LRGB.fits
#   - Plate-solve each process/GLAT*_(LRGB|SHO|HSO).fits with ASTAP
#   - Crop registration border artifacts consistently across all panels
#   - Siril 1.4.0 or later
#   - StarNet++ configured in Preferences -> Miscellaneous
#   - VeraLux_HyperMetric_Stretch.py installed via Scripts -> Get Scripts
#   - VeraLux_StarComposer.py installed via Scripts -> Get Scripts
#   - GraXpert smoothing set to 0.5 in Preferences -> Miscellaneous
#
# SHO workflow (VeraLux Alchemy + manual SPCC)
# --------------------------------------------
# For SHO, run Alchemy and SPCC manually in the GUI before this script,
# then set RUN_SPCC = False in the config section below.
#
# Skip logic
# ----------
# Panels where result_fits/GLAT*_stretched_result.fits already exists are
# skipped. Delete that file to reprocess a panel.

import sirilpy as s
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
HMS_LOG_D     = 3.8    # VeraLux HyperMetric Stretch Log D
SC_STAR_LOG_D = 10.5   # VeraLux StarComposer star intensity Log D

# Set RUN_SPCC = True  to run SPCC automatically (default for LRGB and HSO).
# Set RUN_SPCC = False to skip SPCC -- use this for SHO where you have
# already run colour calibration manually (via VeraLux Alchemy + SPCC in
# the GUI) before running this script. The manual workflow for SHO is:
#   1. Galactic_2_Composite.py  -> produces process/GLAT*_LRGB.fits
#   2. Plate-solve with ASTAP
#   3. Crop registration borders
#   4. Run VeraLux Alchemy manually in Siril GUI
#   5. Run SPCC manually in Siril GUI
#   6. Save the result back to process/GLAT*_LRGB.fits
#   7. Run Galactic_3_Stretch.py with RUN_SPCC = False
RUN_SPCC = True

# Composite suffixes -- matches Galactic_2_Composite SUFFIX_BY_MODE
COMPOSITE_SUFFIXES = ("_LRGB", "_HSO", "_SHO")

# Processing suffixes (based on composite suffix, substituted at runtime)
# These use _LRGB as the template -- replaced with actual suffix per panel
SUFFIX_CC_LINEAR          = "_cc_linear"
SUFFIX_STARLESS           = "_starless"
SUFFIX_STARMASK           = "_starmask"
SUFFIX_STARLESS_STRETCHED = "_starless_stretched"
SUFFIX_RESULT             = "_stretched_result"

STARNET_STARLESS_PREFIX = "starless_"
STARNET_STARMASK_PREFIX = "starmask_"

FITS_EXTENSIONS = {".fits", ".fit", ".fts"}
# ---------------------------------------------------------------------------


def siril_log(siril, msg):
    safe = msg.encode("ascii", errors="replace").decode("ascii")
    if not safe.strip():
        safe = " "
    siril.log(safe)


def cmd_safe(siril, *args):
    try:
        siril.cmd(*args)
        return True
    except Exception as exc:
        siril_log(siril, "  [WARNING] Command failed: " + " ".join(str(a) for a in args))
        siril_log(siril, "            " + str(exc))
        return False


def find_lrgb_panels(home_dir):
    """
    Scan home_dir/process/ for plate-solved GLAT*_(LRGB|HSO|SHO).fits files.
    Returns list of (prefix, composite_suffix, lrgb_path) tuples, sorted by name.
    Skips panels where _stretched_result already exists in home_dir.
    """
    composites_dir = home_dir / "composites"
    if not composites_dir.is_dir():
        return []
    panels = []
    for p in sorted(composites_dir.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in FITS_EXTENSIONS:
            continue
        if not p.stem.startswith("GLAT"):
            continue
        composite_suffix = None
        for s in COMPOSITE_SUFFIXES:
            if p.stem.endswith(s):
                composite_suffix = s
                break
        if composite_suffix is None:
            continue
        prefix = p.stem[: -len(composite_suffix)]
        # Final results go to result_fits/ -- skip if already done
        result = home_dir / "result_fits" / (prefix + composite_suffix + SUFFIX_RESULT + ".fits")
        if result.exists():
            continue
        panels.append((prefix, composite_suffix, p))
    return panels


def process_panel(siril, prefix, composite_suffix, lrgb_path, home_dir):
    """Run steps 1-6 for one plate-solved LRGB panel."""
    siril_log(siril, " ")
    siril_log(siril, "=" * 60)
    siril_log(siril, "Panel: " + prefix + "  [" + composite_suffix.strip("_") + "]")
    siril_log(siril, "Input: " + lrgb_path.name)
    siril_log(siril, "=" * 60)

    process_dir  = home_dir / "process"
    process_dir.mkdir(exist_ok=True)

    # Final results go into dedicated subdirectories under home/
    result_fits_dir = home_dir / "result_fits"
    result_tiff_dir = home_dir / "result_tiff"
    result_fits_dir.mkdir(exist_ok=True)
    result_tiff_dir.mkdir(exist_ok=True)

    # Use composite_suffix as base for all filenames e.g. _LRGB, _HSO, _SHO
    cs = composite_suffix   # shorthand
    result_out   = result_fits_dir / (prefix + cs + SUFFIX_RESULT + ".fits")
    tiff_out     = result_tiff_dir / (prefix + cs + SUFFIX_RESULT + ".tif")

    # Intermediates -> process_dir (kept for diagnosis, no cleanup)
    starless_out       = process_dir / (prefix + cs + SUFFIX_STARLESS + ".fits")
    starmask_out       = process_dir / (prefix + cs + SUFFIX_STARMASK + ".fits")
    stretched_starless = process_dir / (prefix + cs + SUFFIX_STARLESS_STRETCHED + ".fits")
    cc_linear_path     = process_dir / (prefix + cs + SUFFIX_CC_LINEAR + ".fits")

    cmd_safe(siril, "cd", str(home_dir))

    # ------------------------------------------------------------------
    # Step 1: GraXpert Background Extraction then Colour Calibration
    # BGE must run BEFORE SPCC on the linear LRGB image:
    #   - rgbcomp can introduce a gradient even if individual channel
    #     stacks were BGE-corrected (different channel gradients combine
    #     into a residual in the composite)
    #   - SPCC measures stellar photometry across the field; a gradient
    #     makes stars near the bright edge appear brighter, causing SPCC
    #     to overcorrect (the "consider correcting gradient first" warning)
    # Smoothing is set in Preferences -> Miscellaneous -> GraXpert.
    # ------------------------------------------------------------------
    siril_log(siril, "  [1/6] GraXpert background extraction (BGE)...")
    if not cmd_safe(siril, "load", str(lrgb_path)):
        siril_log(siril, "  [ERROR] Cannot load " + lrgb_path.name)
        return False

    bge_ok = cmd_safe(siril, "pyscript", "GraXpert-AI.py", "-bge")
    if not bge_ok:
        siril_log(siril, "  [WARNING] GraXpert BGE failed -- continuing without.")

    # ------------------------------------------------------------------
    # Step 2: GraXpert Denoise
    # Denoise after BGE -- denoiser works better on gradient-free data.
    # ------------------------------------------------------------------
    siril_log(siril, "  [2/6] GraXpert denoise...")
    denoise_ok = cmd_safe(siril, "pyscript", "GraXpert-AI.py", "-denoise", "-strength=0.5")
    if not denoise_ok:
        siril_log(siril, "  [WARNING] GraXpert denoise failed -- continuing.")

    # ------------------------------------------------------------------
    # Step 3: Colour Calibration -- SPCC preferred, PCC with Gaia DR3 fallback
    #
    # Skipped if RUN_SPCC = False (e.g. SHO where Alchemy + SPCC was
    # run manually in the GUI before this script).
    # ------------------------------------------------------------------
    if not RUN_SPCC:
        siril_log(siril, "  [3/6] Colour calibration SKIPPED (RUN_SPCC = False).")
        siril_log(siril, "  Assuming SPCC/Alchemy was already applied manually.")
    else:
        siril_log(siril, "  [3/6] Colour calibration (SPCC -> PCC fallback)...")

        is_narrowband = (
            (home_dir / "Ha" / "stacked").is_dir() or
            (home_dir / "Sii" / "stacked").is_dir() or
            (home_dir / "Oiii" / "stacked").is_dir()
        ) and not (home_dir / "L" / "stacked").is_dir()

        if is_narrowband:
            siril_log(siril, "  Narrowband mode detected -- using SPCC -narrowband")
            cc_ok = cmd_safe(siril, "spcc", "-narrowband")
        else:
            siril_log(siril, "  Wideband mode -- using standard SPCC")
            cc_ok = cmd_safe(siril, "spcc")

        if not cc_ok:
            siril_log(siril, "  SPCC failed -- trying PCC with local Gaia DR3...")
            cc_ok = cmd_safe(siril, "pcc", "-catalog=localgaia")
        if not cc_ok:
            siril_log(siril, "  PCC local failed -- trying remote Gaia...")
            cc_ok = cmd_safe(siril, "pcc", "-catalog=gaia")
        if not cc_ok:
            siril_log(siril, "  [WARNING] All colour calibration failed. Continuing without.")
        else:
            siril_log(siril, "  Colour calibration succeeded.")

    # ------------------------------------------------------------------
    # Step 2: StarNet star removal
    # Save cc_linear then load it so StarNet uses its stem for output names.
    # ------------------------------------------------------------------
    siril_log(siril, "  [4/6] StarNet star removal...")

    if not cmd_safe(siril, "save", str(cc_linear_path)):
        siril_log(siril, "  [ERROR] Cannot save cc_linear.")
        return False
    if not cmd_safe(siril, "load", str(cc_linear_path)):
        siril_log(siril, "  [ERROR] Cannot reload cc_linear.")
        return False

    cmd_safe(siril, "cd", str(process_dir))
    starnet_ok = cmd_safe(siril, "starnet", "-stretch")

    expected_starmask = process_dir / (STARNET_STARMASK_PREFIX + cc_linear_path.stem + ".fits")
    siril_log(siril, "  StarNet ok=" + str(starnet_ok)
              + "  starmask exists=" + str(expected_starmask.exists()))

    has_starmask = False
    if not starnet_ok:
        siril_log(siril, "  [WARNING] StarNet failed -- using full image as starless.")
        starless_path = cc_linear_path
    else:
        if not cmd_safe(siril, "save", str(starless_out)):
            siril_log(siril, "  [ERROR] Cannot save starless.")
            return False
        starless_path = starless_out

        # Find and rename starmask
        for ext in FITS_EXTENSIONS:
            candidate = process_dir / (STARNET_STARMASK_PREFIX + cc_linear_path.stem + ext)
            if candidate.exists():
                try:
                    candidate.replace(starmask_out)
                    has_starmask = True
                    siril_log(siril, "  Starmask: " + starmask_out.name)
                except Exception as exc:
                    siril_log(siril, "  [WARNING] Starmask rename: " + str(exc))
                    starmask_out = candidate
                    has_starmask = True
                break

        if not has_starmask:
            siril_log(siril, "  [WARNING] Starmask not found.")

        siril_log(siril, "  Starless: " + starless_path.name)

    # ------------------------------------------------------------------
    # Step 3: VeraLux HyperMetric Stretch
    # ------------------------------------------------------------------
    siril_log(siril, "  [5/6] VeraLux HyperMetric Stretch (Log D "
              + str(HMS_LOG_D) + ")...")
    siril_log(siril, "  NOTE: Dialog will open -- set Log D to "
              + str(HMS_LOG_D) + " and click Process.")

    if not cmd_safe(siril, "load", str(starless_out)):
        siril_log(siril, "  [ERROR] Cannot load starless for stretching.")
        return False

    hms_ok = cmd_safe(siril, "pyscript", "VeraLux_HyperMetric_Stretch.py")
    if not hms_ok:
        siril_log(siril, "  [WARNING] VeraLux HMS failed -- applying autostretch fallback.")
        cmd_safe(siril, "autostretch")

    # VeraLux writes stretched_<loaded_stem>.fits -- find and rename
    veralux_out = process_dir / ("stretched_" + starless_out.stem + ".fits")
    veralux_alt = process_dir / ("stretched_" + prefix + "_LRGB_starless.fits")
    if not veralux_out.exists() and veralux_alt.exists():
        veralux_out = veralux_alt

    if veralux_out.exists():
        try:
            if veralux_out != stretched_starless:
                veralux_out.rename(stretched_starless)
            siril_log(siril, "  Stretched starless: " + stretched_starless.name)
        except Exception as exc:
            siril_log(siril, "  [WARNING] Cannot rename VeraLux output: " + str(exc))
            stretched_starless = veralux_out
        cmd_safe(siril, "load", str(stretched_starless))
    else:
        siril_log(siril, "  VeraLux output not found -- saving current image.")
        if not cmd_safe(siril, "save", str(stretched_starless)):
            siril_log(siril, "  [ERROR] Cannot save stretched starless.")
            return False

    # ------------------------------------------------------------------
    # Step 4: VeraLux StarComposer
    # ------------------------------------------------------------------
    if has_starmask:
        siril_log(siril, "  [5/6] VeraLux StarComposer...")

        # Create a temp work dir with ONLY the two files StarComposer needs.
        # When the dialog opens browse to this folder -- exactly 2 files,
        # impossible to pick the wrong one. Cleaned up after completion.
        import shutil as _shutil
        work_dir = process_dir / ("_work_" + prefix + cs)
        work_dir.mkdir(exist_ok=True)
        work_starless = work_dir / stretched_starless.name
        work_starmask = work_dir / starmask_out.name
        try:
            _shutil.copy2(stretched_starless, work_starless)
            _shutil.copy2(starmask_out, work_starmask)
            siril_log(siril, "  Starless : " + work_starless.name)
            siril_log(siril, "  Starmask : " + work_starmask.name)
        except Exception as exc:
            siril_log(siril, "  [WARNING] Could not create work dir: " + str(exc))
            siril_log(siril, "  Starless : " + str(stretched_starless))
            siril_log(siril, "  Starmask : " + str(starmask_out))
            work_dir = None
        siril_log(siril, "  Star Intensity Log D: " + str(SC_STAR_LOG_D))

        # cd to work dir so StarComposer opens there directly
        if work_dir:
            cmd_safe(siril, "cd", str(work_dir))

        sc_ok = cmd_safe(siril, "pyscript", "VeraLux_StarComposer.py")

        # Clean up temp work dir
        if work_dir and work_dir.exists():
            try:
                _shutil.rmtree(work_dir)
            except Exception:
                pass

        if not sc_ok:
            siril_log(siril, "  [WARNING] StarComposer failed -- using starless only.")
            cmd_safe(siril, "load", str(stretched_starless))
    else:
        siril_log(siril, "  [5/6] No starmask -- using starless only.")
        cmd_safe(siril, "load", str(stretched_starless))

    # ------------------------------------------------------------------
    # Step 5: Save FITS 32-bit
    # TIFF export is handled by Galactic_4_Tiff.py -- run that after
    # any final manual adjustments to the FITS.
    # ------------------------------------------------------------------
    siril_log(siril, "  [6/6] Saving FITS 32-bit...")
    if not cmd_safe(siril, "save", str(result_out)):
        siril_log(siril, "  [ERROR] Cannot save result FITS.")
        return False
    siril_log(siril, "  Saved: " + result_out.name)
    siril_log(siril, "  Next: run Galactic_4_Tiff.py to export TIFFs for stitching.")

    # Intermediates kept in process/ for diagnosis -- no cleanup
    cmd_safe(siril, "cd", str(home_dir))
    siril_log(siril, "  Panel " + prefix + " complete.")
    return True


def main():
    siril = s.SirilInterface()
    try:
        siril.connect()
        siril_log(siril, "Galactic_3_Stretch v1.0.0 connected.")
    except Exception as exc:
        print("Galactic_3_Stretch: could not connect: " + str(exc))
        return

    try:
        siril.cmd("requires", "1.4.0")
    except Exception:
        siril.error_messagebox("Galactic_3_Stretch requires Siril 1.4.0 or later.")
        siril.disconnect()
        return

    try:
        home_dir = Path(siril.get_siril_wd())
        siril_log(siril, "Home directory: " + str(home_dir))
        siril_log(siril, "Scanning for plate-solved GLAT*_LRGB.fits files...")

        panels = find_lrgb_panels(home_dir)

        if not panels:
            siril_log(siril, "No plate-solved LRGB panels found.")
            siril_log(siril, "Expected: GLAT*_LRGB.fits files in " + str(home_dir / "process"))
            siril_log(siril, "Plate-solve your LRGB files with ASTAP first.")
            siril.disconnect()
            return

        siril_log(siril, "Found " + str(len(panels)) + " panel(s) to process:")
        for prefix, composite_suffix, p in panels:
            siril_log(siril, "  " + p.name)

        ok = fail = 0
        results = []
        for prefix, composite_suffix, lrgb_path in panels:
            if process_panel(siril, prefix, composite_suffix, lrgb_path, home_dir):
                ok += 1
                results.append((prefix + composite_suffix, "OK"))
            else:
                fail += 1
                results.append((prefix + composite_suffix, "FAIL"))

        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "Galactic_3_Stretch complete.")
        siril_log(siril, "=" * 60)
        siril_log(siril, "  {:<20} {:>6}".format("Panel", "Result"))
        siril_log(siril, "  " + "-" * 28)
        for prefix, status in results:
            siril_log(siril, "  {:<20} {:>6}".format(prefix, status))
        siril_log(siril, " ")
        siril_log(siril, "  OK  : " + str(ok)
                  + "   FAIL: " + str(fail)
                  + "   TOTAL: " + str(len(results)))
        siril_log(siril, "  Output: result_fits/GLAT*_stretched_result.fits")
        siril_log(siril, "  Next: make any final adjustments, then run Galactic_4_Tiff.py")
        siril_log(siril, "=" * 60)

    except Exception as exc:
        siril_log(siril, "Unhandled error: " + str(exc))
        traceback.print_exc()
    finally:
        # Always return to home directory on exit or interrupt
        try:
            home_dir = Path(siril.get_siril_wd())
            siril.cmd("cd", str(home_dir))
        except Exception:
            pass
        siril.disconnect()


main()