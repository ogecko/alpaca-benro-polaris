# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_3_Stretch.py
# Version: 1.0.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# Description
# -----------
# Processes plate-solved GLAT*_LRGB.fits files in the home directory through:
#   1.  SPCC colour calibration (falls back to PCC with Gaia DR3)
#   2.  StarNet star removal (saves starless + starmask)
#   3.  VeraLux HyperMetric Stretch on starless (dialog -- set Log D 3.8)
#   4.  VeraLux StarComposer (dialog -- select both files shown in log)
#   5.  Save FITS 32-bit  GLAT*_LRGB_stretched_result.fits
#   6.  Save TIFF 16-bit  GLAT*_LRGB_stretched_result.tif
#
# Prerequisites
# -------------
#   - Run Galactic_2_Recompose.py first to produce the GLAT*_LRGB.fits files
#   - Plate-solve each GLAT*_LRGB.fits with ASTAP before running this script
#   - Siril 1.4.0 or later
#   - StarNet++ configured in Preferences -> Miscellaneous
#   - VeraLux_HyperMetric_Stretch.py installed via Scripts -> Get Scripts
#   - VeraLux_StarComposer.py installed via Scripts -> Get Scripts
#
# Skip logic
# ----------
# Panels where GLAT*_LRGB_stretched_result.fits already exists are skipped.
# Delete that file to reprocess a panel.

import sirilpy as s
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
HMS_LOG_D    = 3.8     # VeraLux HyperMetric Stretch Log D
SC_STAR_LOG_D = 10.5   # VeraLux StarComposer star intensity Log D

SUFFIX_LRGB              = "_LRGB"
SUFFIX_CC_LINEAR         = "_LRGB_cc_linear"
SUFFIX_STARLESS          = "_LRGB_starless"
SUFFIX_STARMASK          = "_LRGB_starmask"
SUFFIX_STARLESS_STRETCHED = "_LRGB_starless_stretched"
SUFFIX_RESULT            = "_LRGB_stretched_result"

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
    Scan home_dir/process/ for plate-solved GLAT*_LRGB.fits files.
    Returns list of (prefix, lrgb_path) tuples, sorted by prefix.
    Skips panels where _stretched_result already exists in home_dir.
    """
    process_dir = home_dir / "process"
    if not process_dir.is_dir():
        return []
    panels = []
    for p in sorted(process_dir.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in FITS_EXTENSIONS:
            continue
        if not p.stem.startswith("GLAT"):
            continue
        if not p.stem.endswith(SUFFIX_LRGB):
            continue
        prefix = p.stem[: -len(SUFFIX_LRGB)]
        # Final results go to home_dir -- skip if already done
        result = home_dir / (prefix + SUFFIX_RESULT + ".fits")
        if result.exists():
            continue
        panels.append((prefix, p))
    return panels


def process_panel(siril, prefix, lrgb_path, home_dir):
    """Run steps 1-6 for one plate-solved LRGB panel."""
    siril_log(siril, " ")
    siril_log(siril, "=" * 60)
    siril_log(siril, "Panel: " + prefix)
    siril_log(siril, "Input: " + lrgb_path.name)
    siril_log(siril, "=" * 60)

    process_dir  = home_dir / "process"
    process_dir.mkdir(exist_ok=True)

    # Final results -> home_dir (visible alongside LRGB files for easy access)
    result_out   = home_dir / (prefix + SUFFIX_RESULT + ".fits")
    tiff_out     = home_dir / (prefix + SUFFIX_RESULT + ".tif")

    # Intermediates -> process_dir (kept for diagnosis, no cleanup)
    starless_out       = process_dir / (prefix + SUFFIX_STARLESS + ".fits")
    starmask_out       = process_dir / (prefix + SUFFIX_STARMASK + ".fits")
    stretched_starless = process_dir / (prefix + SUFFIX_STARLESS_STRETCHED + ".fits")
    cc_linear_path     = process_dir / (prefix + SUFFIX_CC_LINEAR + ".fits")

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
    siril_log(siril, "  [1/8] GraXpert background extraction (BGE)...")
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
    siril_log(siril, "  [2/8] GraXpert denoise...")
    denoise_ok = cmd_safe(siril, "pyscript", "GraXpert-AI.py", "-denoise", "-strength=0.5")
    if not denoise_ok:
        siril_log(siril, "  [WARNING] GraXpert denoise failed -- continuing.")

    # ------------------------------------------------------------------
    # Step 3: Colour Calibration -- SPCC preferred, PCC with Gaia DR3 fallback
    # ------------------------------------------------------------------
    siril_log(siril, "  [3/8] Colour calibration (SPCC -> PCC fallback)...")
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
    siril_log(siril, "  [4/8] StarNet star removal...")

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
    siril_log(siril, "  [5/8] VeraLux HyperMetric Stretch (Log D "
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
        siril_log(siril, "  [6/8] VeraLux StarComposer...")
        siril_log(siril, "  *** SELECT BOTH FILES IN THE DIALOG ***")
        siril_log(siril, "  Starless : " + str(stretched_starless))
        siril_log(siril, "  Starmask : " + str(starmask_out))
        siril_log(siril, "  Star Intensity Log D: " + str(SC_STAR_LOG_D))
        sc_ok = cmd_safe(siril, "pyscript", "VeraLux_StarComposer.py")
        if not sc_ok:
            siril_log(siril, "  [WARNING] StarComposer failed -- using starless only.")
            cmd_safe(siril, "load", str(stretched_starless))
    else:
        siril_log(siril, "  [6/8] No starmask -- using starless only.")
        cmd_safe(siril, "load", str(stretched_starless))

    # ------------------------------------------------------------------
    # Step 5: Save FITS 32-bit
    # ------------------------------------------------------------------
    siril_log(siril, "  [7/8] Saving FITS 32-bit...")
    if not cmd_safe(siril, "save", str(result_out)):
        siril_log(siril, "  [ERROR] Cannot save result FITS.")
        return False
    siril_log(siril, "  Saved: " + result_out.name)

    # ------------------------------------------------------------------
    # Step 6: Save TIFF 16-bit
    # ------------------------------------------------------------------
    siril_log(siril, "  [8/8] Saving TIFF 16-bit...")
    if not cmd_safe(siril, "savetif", str(tiff_out.with_suffix(""))):
        siril_log(siril, "  [WARNING] TIFF save failed.")
    else:
        siril_log(siril, "  Saved: " + tiff_out.name)

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
        for prefix, p in panels:
            siril_log(siril, "  " + p.name)

        ok = fail = 0
        results = []
        for prefix, lrgb_path in panels:
            if process_panel(siril, prefix, lrgb_path, home_dir):
                ok += 1
                results.append((prefix, "OK"))
            else:
                fail += 1
                results.append((prefix, "FAIL"))

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
        siril_log(siril, "  Output: GLAT*_LRGB_stretched_result.fits/.tif in home/")
        siril_log(siril, "=" * 60)

    except Exception as exc:
        siril_log(siril, "Unhandled error: " + str(exc))
        traceback.print_exc()
    finally:
        siril.disconnect()


main()