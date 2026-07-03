# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_3_Stretch.py
# Version: 1.2.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# Description
# -----------
# Processes plate-solved GLAT*_(LRGB|SHO|HSO).fits files from composites/
# through the full stretch pipeline. Optional steps are controlled by
# RUN_* flags in the CONFIGURATION section below.
#
# Steps (all 6 always logged; skipped steps say "skipped"):
#
#   [1/6]  GraXpert BGE          -- optional: RUN_BGE = True (default)
#          Background extraction on the linear LRGB before SPCC.
#
#   [2/6]  GraXpert Denoise      -- optional: RUN_DENOISE = True (default)
#          Denoising after BGE on gradient-free data.
#
#   [3/6]  SPCC colour calibration -- optional: RUN_SPCC = True (default)
#          Auto-detects wideband (LRGB) vs narrowband (SHO/HSO).
#          Set False for SHO after running VeraLux Alchemy manually.
#
#   [4/6]  StarNet star removal  -- optional: RUN_STARNET = True (default)
#   [5/6]  VeraLux HMS + StarComposer
#          If RUN_STARNET = False: both StarNet and StarComposer are skipped.
#          VeraLux HMS runs on the full image (stars included) -- no starmask.
#          If RUN_STARNET = True: HMS runs on starless, StarComposer recombines.
#
#   [6/6]  Save 32-bit FITS -> result_fits/GLAT*_stretched_result.fits
#
# Prerequisites
# -------------
#   - Run Galactic_2_Composite.py first -> composites/GLAT*_(LRGB|SHO|HSO).fits
#   - Plate-solve each composite with ASTAP
#   - Crop registration border artifacts consistently across all panels
#   - Siril 1.4.0 or later
#   - StarNet++ configured in Preferences -> Miscellaneous (only if RUN_STARNET)
#   - VeraLux_HyperMetric_Stretch.py installed via Scripts -> Get Scripts
#   - VeraLux_StarComposer.py installed via Scripts -> Get Scripts (if RUN_STARNET)
#   - GraXpert smoothing set to 0.5 in Preferences -> Miscellaneous (if RUN_BGE)
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

# Optional processing steps -- set False to skip
RUN_BGE     = True   # GraXpert background extraction before SPCC
RUN_DENOISE = False   # GraXpert denoise after BGE
# If RUN_STARNET = False, StarNet and StarComposer are both skipped.
# VeraLux HyperMetric Stretch runs on the full image (stars included).
RUN_STARNET = True   # StarNet star removal + VeraLux StarComposer

# Set RUN_SPCC = True  to run SPCC automatically (default for LRGB and HSO).
# Set RUN_SPCC = False to skip SPCC -- use this for SHO where you have
# already run colour calibration manually (via VeraLux Alchemy + SPCC in
# the GUI) before running this script. The manual workflow for SHO is:
#   1. Galactic_2_Composite.py  -> produces composites/GLAT*_LRGB.fits
#   2. Plate-solve with ASTAP
#   3. Crop registration borders
#   4. Run VeraLux Alchemy manually in Siril GUI
#   5. Run SPCC manually in Siril GUI
#   6. Save the result back to composites/GLAT*_LRGB.fits
#   7. Run Galactic_3_Stretch.py with RUN_SPCC = False
RUN_SPCC = True

# BYPASS_VERALUX_HMS = True skips the VeraLux GUI entirely and uses a
# headless Python equivalent of the HyperMetric Stretch algorithm.
# This eliminates the Cairo/icc_remove crash that can occur when VeraLux
# opens its dialog inside a scripted pipeline. The math is identical to
# VeraLux HMS v1.5.x (IHS with vector colour preservation).
# Parameters below map directly to the VeraLux GUI controls.
BYPASS_VERALUX_HMS = False   # True = headless stretch, False = VeraLux GUI
HMS_TARGET_BG  = 0.15        # Target background median (VeraLux "Target Bg")
HMS_PROTECT_B  = 6.0         # Highlight protection (VeraLux "Protect b")
HMS_COLOR_GRIP = 0.0         # 0.0=scientific vector preserve, 1.0=scalar stretch

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


# ---------------------------------------------------------------------------
# Headless VeraLux HyperMetric Stretch equivalent
# ---------------------------------------------------------------------------
def hms_stretch(fits_path, out_path, log_d, target_bg, protect_b, color_grip):
    """
    Headless equivalent of VeraLux HyperMetric Stretch v1.5.x.

    Algorithm (faithful to VeraLux source + author's published description):
      1. Load image from fits_path (32-bit float, values in [0,1])
      2. Normalise to [0,1] if values exceed 1.0 (StarNet rescaling artefact)
      3. Extract luminance: L = mean(R, G, B)  [equal weights, no sensor QE]
      4. Apply Inverse Hyperbolic Stretch (IHS) to L:
            b    = 10 ** (-protect_b)         # shadow protection value
            D    = 10 ** log_d                 # stretch factor
            norm = arcsinh(D*(1-SP)+b) - arcsinh(b)  where SP=0
            L_s  = (arcsinh(D*L + b) - arcsinh(b)) / norm
      5. Project stretched luminance back to RGB (vector colour preservation):
            Scientific (color_grip=0.0): each channel *= L_s / L
            Scalar     (color_grip=1.0): IHS applied to each channel independently
            Blend for  0 < color_grip < 1
      6. Clip to [0,1], save to out_path

    Parameters
    ----------
    fits_path  : Path  -- input FITS file (linear, 32-bit, [0,1])
    out_path   : Path  -- output FITS file
    log_d      : float -- stretch intensity (HMS_LOG_D, default 3.8)
    target_bg  : float -- target background median (HMS_TARGET_BG, 0.15)
                          Note: with a fixed log_d the target_bg parameter
                          documents intent but doesn't auto-solve D here --
                          use HMS_LOG_D to control stretch strength directly.
    protect_b  : float -- highlight protection (HMS_PROTECT_B, 6.0)
    color_grip : float -- 0.0=scientific vector preserve, 1.0=scalar (HMS_COLOR_GRIP)

    Returns True on success, False on error.
    """
    try:
        import numpy as np
        from astropy.io import fits as _afits

        with _afits.open(str(fits_path)) as hdul:
            header = hdul[0].header.copy()
            data   = hdul[0].data.astype(np.float64)  # (3,H,W) or (H,W)

        mono = data.ndim == 2
        if mono:
            data = data[np.newaxis]   # (1,H,W)

        # Normalise if values exceed 1.0
        max_val = data.max()
        if max_val > 1.0:
            data = data / max_val

        n_ch = data.shape[0]

        # Luminance proxy (equal weights)
        if n_ch >= 3:
            L = (data[0] + data[1] + data[2]) / 3.0
        else:
            L = data[0].copy()

        # IHS parameters
        D  = 10.0 ** log_d
        b  = 10.0 ** (-protect_b)   # small positive value ~1e-6 for protect_b=6
        SP = 0.0

        arcsinh_b    = np.arcsinh(b)
        arcsinh_norm = np.arcsinh(D * (1.0 - SP) + b) - arcsinh_b
        if abs(arcsinh_norm) < 1e-12:
            arcsinh_norm = 1e-12

        def ihs(x):
            return (np.arcsinh(D * np.clip(x - SP, 0, None) + b) - arcsinh_b) / arcsinh_norm

        L_s = ihs(L)

        eps = 1e-12
        if n_ch >= 3:
            # Scientific mode: preserve channel ratios exactly
            ratio = np.where(L > eps, L_s / (L + eps), L_s / (eps))
            img_sci = np.stack([
                np.clip(data[c] * ratio, 0.0, 1.0) for c in range(n_ch)
            ])

            if color_grip > 0.0:
                # Scalar mode: each channel stretched independently
                img_scalar = np.stack([
                    np.clip(ihs(data[c]), 0.0, 1.0) for c in range(n_ch)
                ])
                out = (1.0 - color_grip) * img_sci + color_grip * img_scalar
            else:
                out = img_sci
        else:
            out = np.clip(L_s[np.newaxis], 0.0, 1.0)

        if mono:
            out = out[0]

        out_hdu = _afits.PrimaryHDU(out.astype(np.float32), header=header)
        out_hdu.writeto(str(out_path), overwrite=True)
        return True

    except Exception as exc:
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
    # Steps 1-2: GraXpert BGE and Denoise (both optional via RUN_ flags)
    # BGE should run before SPCC on the linear LRGB image -- a gradient
    # biases SPCC's stellar photometry causing overcorrection.
    # Denoise after BGE works better on gradient-free data.
    # ------------------------------------------------------------------
    if not cmd_safe(siril, "load", str(lrgb_path)):
        siril_log(siril, "  [ERROR] Cannot load " + lrgb_path.name)
        return False

    if RUN_BGE:
        siril_log(siril, "  [1/6] GraXpert background extraction (BGE)...")
        bge_ok = cmd_safe(siril, "pyscript", "GraXpert-AI.py", "-bge")
        if not bge_ok:
            siril_log(siril, "  [WARNING] GraXpert BGE failed -- continuing.")
    else:
        siril_log(siril, "  [1/6] BGE skipped (RUN_BGE = False).")

    if RUN_DENOISE:
        siril_log(siril, "  [2/6] GraXpert denoise...")
        denoise_ok = cmd_safe(siril, "pyscript", "GraXpert-AI.py", "-denoise", "-strength=0.5")
        if not denoise_ok:
            siril_log(siril, "  [WARNING] GraXpert denoise failed -- continuing.")
    else:
        siril_log(siril, "  [2/6] Denoise skipped (RUN_DENOISE = False).")

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
    # Steps 4-5: StarNet + VeraLux HyperMetric Stretch + StarComposer
    # If RUN_STARNET = False: StarNet and StarComposer are both skipped.
    # VeraLux HMS runs on the full image (stars included).
    # ------------------------------------------------------------------

    # Always save cc_linear for diagnosis regardless of StarNet
    if not cmd_safe(siril, "save", str(cc_linear_path)):
        siril_log(siril, "  [ERROR] Cannot save cc_linear.")
        return False

    if RUN_STARNET:
        siril_log(siril, "  [4/6] StarNet star removal...")
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
            siril_log(siril, "  [WARNING] StarNet failed -- stretching full image.")
            # Load cc_linear as the image to stretch
            cmd_safe(siril, "load", str(cc_linear_path))
            stretch_source = cc_linear_path
        else:
            if not cmd_safe(siril, "save", str(starless_out)):
                siril_log(siril, "  [ERROR] Cannot save starless.")
                return False
            stretch_source = starless_out

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
            siril_log(siril, "  Starless: " + stretch_source.name)

        # Step 5a: HyperMetric Stretch on starless
        siril_log(siril, "  [5/6] HyperMetric Stretch (Log D " + str(HMS_LOG_D) + ")...")

        if BYPASS_VERALUX_HMS:
            siril_log(siril, "  Headless HMS (BYPASS_VERALUX_HMS = True)...")
            if hms_stretch(stretch_source, stretched_starless,
                           HMS_LOG_D, HMS_TARGET_BG, HMS_PROTECT_B, HMS_COLOR_GRIP):
                siril_log(siril, "  Headless HMS complete: " + stretched_starless.name)
                if not cmd_safe(siril, "load", str(stretched_starless)):
                    siril_log(siril, "  [ERROR] Cannot load headless stretch result.")
                    return False
            else:
                siril_log(siril, "  [ERROR] Headless HMS failed.")
                return False
        else:
            siril_log(siril, "  NOTE: Dialog will open -- set Log D to "
                      + str(HMS_LOG_D) + " and click Process.")
            if not cmd_safe(siril, "load", str(stretch_source)):
                siril_log(siril, "  [ERROR] Cannot load image for stretching.")
                return False
            cmd_safe(siril, "cd", str(process_dir))
            hms_ok = cmd_safe(siril, "pyscript", "VeraLux_HyperMetric_Stretch.py")
            if not hms_ok:
                siril_log(siril, "  [WARNING] VeraLux HMS failed -- applying autostretch fallback.")
                cmd_safe(siril, "autostretch")

            veralux_stem = "stretched_" + stretch_source.stem + ".fits"
            veralux_out = None
            for search_dir in (process_dir, home_dir):
                candidate = search_dir / veralux_stem
                if candidate.exists():
                    veralux_out = candidate
                    break
            if veralux_out is None:
                for alt_name in (prefix + cs + "_starless", prefix + cs + "starless"):
                    for sd in (process_dir, home_dir):
                        alt = sd / ("stretched_" + alt_name + ".fits")
                        if alt.exists():
                            veralux_out = alt
                            break

            if veralux_out and veralux_out.exists():
                try:
                    if veralux_out != stretched_starless:
                        veralux_out.rename(stretched_starless)
                    siril_log(siril, "  Stretched: " + stretched_starless.name)
                except Exception as exc:
                    siril_log(siril, "  [WARNING] Cannot rename VeraLux output: " + str(exc))
                    stretched_starless = veralux_out
                cmd_safe(siril, "load", str(stretched_starless))
            else:
                siril_log(siril, "  VeraLux output not found -- saving current image.")
                if not cmd_safe(siril, "save", str(stretched_starless)):
                    siril_log(siril, "  [ERROR] Cannot save stretched image.")
                    return False

        # Step 5b: VeraLux StarComposer (only if we have a starmask)
        if has_starmask:
            import shutil as _shutil
            work_dir = process_dir / ("_work_" + prefix + cs)
            work_dir.mkdir(exist_ok=True)
            work_starless = work_dir / stretched_starless.name
            work_starmask = work_dir / starmask_out.name
            try:
                _shutil.copy2(stretched_starless, work_starless)
                _shutil.copy2(starmask_out, work_starmask)
                siril_log(siril, "  StarComposer -- Starless : " + work_starless.name)
                siril_log(siril, "  StarComposer -- Starmask : " + work_starmask.name)
            except Exception as exc:
                siril_log(siril, "  [WARNING] Could not create work dir: " + str(exc))
                siril_log(siril, "  Starless : " + str(stretched_starless))
                siril_log(siril, "  Starmask : " + str(starmask_out))
                work_dir = None
            siril_log(siril, "  Star Intensity Log D: " + str(SC_STAR_LOG_D))

            if work_dir:
                cmd_safe(siril, "cd", str(work_dir))

            sc_ok = cmd_safe(siril, "pyscript", "VeraLux_StarComposer.py")

            # Always clean up work dir
            cmd_safe(siril, "cd", str(process_dir))
            if work_dir and work_dir.exists():
                try:
                    _shutil.rmtree(work_dir)
                except Exception:
                    pass

            if not sc_ok:
                siril_log(siril, "  [WARNING] StarComposer failed -- using starless only.")
                cmd_safe(siril, "load", str(stretched_starless))
        else:
            siril_log(siril, "  No starmask -- using starless only.")
            cmd_safe(siril, "load", str(stretched_starless))

    else:
        # RUN_STARNET = False: stretch the full image (stars included)
        siril_log(siril, "  [4/6] StarNet skipped (RUN_STARNET = False).")
        siril_log(siril, "  [5/6] HyperMetric Stretch on full image (Log D "
                  + str(HMS_LOG_D) + ")...")

        if BYPASS_VERALUX_HMS:
            siril_log(siril, "  Headless HMS (BYPASS_VERALUX_HMS = True)...")
            if hms_stretch(cc_linear_path, stretched_starless,
                           HMS_LOG_D, HMS_TARGET_BG, HMS_PROTECT_B, HMS_COLOR_GRIP):
                siril_log(siril, "  Headless HMS complete: " + stretched_starless.name)
                if not cmd_safe(siril, "load", str(stretched_starless)):
                    siril_log(siril, "  [ERROR] Cannot load headless stretch result.")
                    return False
            else:
                siril_log(siril, "  [ERROR] Headless HMS failed.")
                return False
        else:
            siril_log(siril, "  NOTE: Dialog will open -- set Log D to "
                      + str(HMS_LOG_D) + " and click Process.")
            if not cmd_safe(siril, "load", str(cc_linear_path)):
                siril_log(siril, "  [ERROR] Cannot load cc_linear for stretching.")
                return False
            cmd_safe(siril, "cd", str(process_dir))
            hms_ok = cmd_safe(siril, "pyscript", "VeraLux_HyperMetric_Stretch.py")
            if not hms_ok:
                siril_log(siril, "  [WARNING] VeraLux HMS failed -- applying autostretch fallback.")
                cmd_safe(siril, "autostretch")

            veralux_stem = "stretched_" + cc_linear_path.stem + ".fits"
            veralux_out = None
            for search_dir in (process_dir, home_dir):
                candidate = search_dir / veralux_stem
                if candidate.exists():
                    veralux_out = candidate
                    break
            if veralux_out and veralux_out.exists():
                try:
                    veralux_out.rename(stretched_starless)
                    cmd_safe(siril, "load", str(stretched_starless))
                except Exception:
                    pass
            else:
                cmd_safe(siril, "save", str(stretched_starless))

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