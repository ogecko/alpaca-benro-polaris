# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_3_Stretch.py
# Version: 6.0.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# ==============================================================================
# OVERVIEW
# ==============================================================================
# Processes each plate-solved composite from composites/ into a final
# stretched result, ready for Galactic_4_Tiff.py. Runs in two passes over
# every queued panel (see PASS 1/2 and PASS 2/2 in main()), so that
# RUN_STAR_HARMONIZE can compare every panel's linear star layer before
# any of them are stretched:
#
# PASS 1/2 (steps 1-4, process_panel_part1):
#   1. SPCC colour calibration                (optional, RUN_SPCC)
#   2. RC-Astro BlurXTerminator                (optional, RUN_BLURXTERMINATOR)
#   3. RC-Astro NoiseXTerminator               (optional, RUN_NOISEXTERMINATOR)
#   4. RC-Astro StarXTerminator                (optional, RUN_STARXTERMINATOR)
#      -- splits the composite into stars_*.fits / stars_none_*.fits in
#      star_removal/.
#
# Between passes: cross-panel star brightness harmonization (optional,
# RUN_STAR_HARMONIZE) -- compares every panel's stars_*.fits from pass 1
# and computes a per-panel linear gain, applied in pass 2 before the Log D
# stretch (see that config comment for why).
#
# PASS 2/2 (steps 5-7, process_panel_part2):
#   5. Statistical stretch (see STAT_* below), applied to stars_none_*.fits
#      if StarXTerminator ran, otherwise to the composite itself, then
#      saved to result_fits/GLAT*_stretched_result.fits. If StarXTerminator
#      ran, stars_none_*.fits is updated with this stretched result too, so
#      star_removal/ always holds the stretched starless + linear stars
#      pair, kept untouched by steps 6-7 below -- e.g. to run Narrowband
#      Neutralisation on stars_none_*.fits manually and recombine yourself
#      in the VeraLux StarComposer GUI, instead of the automatic steps.
#   6. Narrowband Normalization                (optional, RUN_NARROWBAND_NORMALIZATION)
#      -- _SHO/_HSO composites only (palette chosen automatically from the
#      panel's own composite suffix); applied to result_out and, if step 4
#      ran, to stars_none_*.fits too.
#   7. VeraLux StarComposer recombination      (optional, RUN_VERALUX_RECOMBINE)
#      -- only runs when step 4 produced a stars_*/stars_none_* pair;
#      recombines them with a headless port of VeraLux StarComposer's own
#      maths (including the harmonization gain from between the passes)
#      and OVERWRITES result_fits/GLAT*_stretched_result.fits with the
#      recombined (stars back in) result.
#
# With RUN_STARXTERMINATOR = False, no panel ever has a star layer, so
# harmonization between the passes is always a no-op and pass 2 behaves
# exactly as a single-pass run of steps 5-6 always has.
#
# Steps 2-4 run via Siril's `pyscript` command, which drives RC-Astro's
# stand-alone command-line tool through the BlurXTerminator.py /
# NoiseXTerminator.py / StarXTerminator.py scripts. RC-Astro is a separate,
# licensed product from https://www.rc-astro.com and must be installed and
# licensed independently; these scripts must be discoverable by Siril's
# `pyscript` command (working directory, user script paths, or the
# siril-scripts repo).
#
# Steps 6 and 7 do NOT call the NarrowbandNormalization.py / VeraLux
# StarComposer.py scripts themselves (both are GUI-only, with no
# headless/CLI mode) -- instead their own maths (process_image() for step
# 6, VeraLuxCore + process_star_pipeline for step 7) is ported directly
# into this script below, driven by the NBN_* / VERALUX_* config instead
# of sliders.
#
# Prerequisites
# -------------
#   Siril 1.4.0 or later.
#   Run Galactic_2_Composite.py first, then plate-solve each composite
#   with ASTAP.
#
# SHO workflow
# ------------
# For SHO, run VeraLux Alchemy and SPCC manually in the GUI before this
# script, then set RUN_SPCC = False below.
#
# Skip logic
# ----------
# Panels where result_fits/GLAT*_stretched_result.fits already exists are
# filtered out before pass 1 even starts. Delete that file to reprocess a
# panel.

import sirilpy as s

s.ensure_installed("numpy", "astropy", "opencv-python")

import shutil
import traceback
import math
from pathlib import Path

import numpy as np
import cv2
from astropy.io import fits as _afits


# ==============================================================================
# CONFIGURATION
# ==============================================================================

# ------------------------------------------------------------------------
# Directory layout / file matching (used throughout)
# ------------------------------------------------------------------------
COMPOSITE_SUFFIXES = ("_LRGB", "_HSO", "_SHO")   # matches Galactic_2_Composite SUFFIX_BY_MODE

SUFFIX_CC_LINEAR = "_cc_linear"         # post-BGE/SPCC linear result, kept for diagnosis
SUFFIX_RESULT    = "_stretched_result"

STAR_WORKING_DIR = "star_removal"       # holds stars_*.fits / stars_none_*.fits

FITS_EXTENSIONS = {".fits", ".fit", ".fts"}

# ------------------------------------------------------------------------
# Step 1: SPCC colour calibration -- RUN_SPCC
# ------------------------------------------------------------------------
# For SHO, set False once colour calibration has been done manually (see
# "SHO workflow" above).
RUN_SPCC = True

# Sensor and filter names MUST match exactly (case and spacing) the names in
# Siril's SPCC dialog combo boxes. Find the exact strings for your gear by
# running these in Siril's own command line:
#   spcc_list monosensor      (or oscsensor for one-shot-colour cameras)
#   spcc_list redfilter / greenfilter / bluefilter
# Setting these here means SPCC always uses the values below rather than
# whatever was last selected in the GUI.
SPCC_SENSOR_MODE = "mono"     # "mono" or "osc"

# -- mono sensor + per-channel filters (used when SPCC_SENSOR_MODE="mono") --
SPCC_MONO_SENSOR = "Sony IMX585"   # exact name from `spcc_list monosensor`
SPCC_RFILTER     = "Optolong R"    # exact name from `spcc_list redfilter`
SPCC_GFILTER     = "Optolong G"    # exact name from `spcc_list greenfilter`
SPCC_BFILTER     = "Optolong B"    # exact name from `spcc_list bluefilter`

# -- OSC sensor (used when SPCC_SENSOR_MODE="osc") --
SPCC_OSC_SENSOR = ""     # exact name from `spcc_list oscsensor`
SPCC_OSC_FILTER = ""     # exact name from `spcc_list oscfilter` (optional)
SPCC_OSC_LPF    = ""     # exact name from `spcc_list osclpf` (optional)

SPCC_WHITEREF = ""   # exact name from `spcc_list whiteref`; blank = Siril default

# Background tolerance for SPCC's own automatic background sampling (used
# internally for its background-neutralisation step). Tightening this
# (smaller values = more conservative, only very dim/uniform pixels count as
# background) makes SPCC's background selection -- and so its calibration --
# more consistent panel to panel. Format is "lower,upper"; blank = Siril default.
SPCC_BGTOL = ""    # e.g. "0.01,0.1"

# -- Narrowband filters (nm), used automatically for _SHO / _HSO composites --
# SPCC is run in Narrowband mode (-narrowband -rwl= -rbw= ... in Siril's spcc
# command) for these, with these wavelengths/bandwidths mapped to R/G/B by
# the composite's own channel order rather than relying on whatever
# broadband filter names or narrowband values were last set in the SPCC
# dialog:
#   _SHO composite -> R=Sii, G=Ha, B=Oiii
#   _HSO composite -> R=Ha,  G=Sii, B=Oiii
# _LRGB composites are unaffected and keep using the broadband
# SPCC_SENSOR_MODE / SPCC_*FILTER settings above.
SII_WAVELENGTH  = 671.6
SII_BANDWIDTH   = 7.0
HA_WAVELENGTH   = 656.3
HA_BANDWIDTH    = 7.0
OIII_WAVELENGTH = 500.7
OIII_BANDWIDTH  = 7.0

# ------------------------------------------------------------------------
# Step 2: RC-Astro BlurXTerminator -- RUN_BLURXTERMINATOR
# ------------------------------------------------------------------------
# Runs after SPCC, via `pyscript BlurXTerminator.py`. Requires RC-Astro's
# stand-alone CLI to be installed and licensed (https://www.rc-astro.com).
RUN_BLURXTERMINATOR = True

BXT_SHARPEN_STARS      = 0.1     # --ss    (0.0 - 0.7)
BXT_ADJUST_STAR_HALOS  = -0.5    # --ash   (-0.5 - 0.5)
BXT_AUTOMATIC_PSF      = True    # --ansp / --no-ansp (Auto Nonstellar PSF)
BXT_SHARPEN_NONSTELLAR = 0.156   # --sn    (0.0 - 1.0)
BXT_CORRECT_ONLY       = False   # --correct-only; when True every other
                                  # BXT_* setting above is ignored (pinned
                                  # by the tool itself) and only PSF
                                  # aberration correction is applied.
# Only used if BXT_AUTOMATIC_PSF is False (manual nonstellar PSF diameter,
# in pixels, 0.0 - 8.0):
BXT_NONSTELLAR_RADIUS = 0.0

# ------------------------------------------------------------------------
# Step 3: RC-Astro NoiseXTerminator -- RUN_NOISEXTERMINATOR
# ------------------------------------------------------------------------
# Runs after SPCC / BlurXTerminator, via `pyscript NoiseXTerminator.py`.
RUN_NOISEXTERMINATOR = True

NXT_DENOISE    = 0.9   # --dn (0.0 - 1.0)
NXT_ITERATIONS = 2     # --it (1 - 5)
# Color Separation / Frequency Separation are GUI-only switches in
# NoiseXTerminator's own schema -- RC-Astro doesn't expose a CLI flag for
# them, so they are always off when run headless via pyscript regardless of
# these values. Kept here as documentation of the intended (and only
# reachable) setting.
NXT_COLOR_SEPARATION     = False
NXT_FREQUENCY_SEPARATION = False

# ------------------------------------------------------------------------
# Step 4: RC-Astro StarXTerminator -- RUN_STARXTERMINATOR
# ------------------------------------------------------------------------
# Runs after SPCC / BlurXTerminator / NoiseXTerminator, via
# `pyscript StarXTerminator.py --stars`. Splits the composite into a
# starless image and a stars-only image.
#
#   - If False: the statistical stretch (step 5) is applied directly to the
#     composite, as in previous versions of this script.
#   - If True: both images are saved into star_removal/ as
#     stars_<panel>.fits (stars only, untouched) and
#     stars_none_<panel>.fits (starless, about to be stretched). The
#     stretch is then applied ONLY to stars_none_<panel>.fits, so the two
#     can be recombined afterwards with VeraLux StarComposer.
RUN_STARXTERMINATOR = True

STARXTERMINATOR_UNSCREEN = False   # --unscreen (unscreen the stars image)

# ------------------------------------------------------------------------
# Step 5: Statistical stretch
# ------------------------------------------------------------------------
# Headless port of Cyril Richard's Seti Astro Statistical Stretch script
# (the maths in StatisticalStretchProcessor below is unchanged from that
# script; only the GUI/CLI wrapper has been stripped out and replaced with
# the config values here so it can run unattended per panel).
STAT_TARGET_MEDIAN        = 0.20    # Target median (0.01 - 0.99)
STAT_NO_BLACK_CLIP        = False   # No black clipping
STAT_LINKED_STRETCH       = False   # Linked stretch (RGB channels together)
STAT_NORMALIZE            = True    # Normalize
STAT_HDR_COMPRESS         = False   # Enable HDR highlight compress
STAT_HDR_AMOUNT           = 0.15    # HDR Amount (0.0 - 1.0)
STAT_HDR_KNEE             = 0.30    # HDR Knee (0.1 - 0.95)
STAT_APPLY_CURVES_BOOST   = False   # Apply curves boost
STAT_CURVES_BOOST_STRENGTH = 0.00   # Curves boost strength (0.0 - 1.0)

# Not exposed in the dialog's main panel but required by the algorithm
# (black-point sigma clip, "Black point sigma" slider there): sigma below
# the robust background median used to find the black point, unless
# STAT_NO_BLACK_CLIP is True. 5.0 matches the dialog's own default.
STAT_BLACKPOINT_SIGMA = 5.0

# ------------------------------------------------------------------------
# Step 6: Narrowband Normalization -- RUN_NARROWBAND_NORMALIZATION
# ------------------------------------------------------------------------
# Runs after the stretch (step 5), before VeraLux recombination (step 7),
# and only for _SHO/_HSO composites -- the palette is chosen automatically
# from the panel's own composite suffix (SHO or HSO), matching the R/G/B
# channel order SPCC (step 1) already calibrated them into, so there's
# nothing to set manually here. Applied to result_out, and also to
# star_removal/stars_none_*.fits if StarXTerminator ran, so VeraLux
# recombination (step 7) still composites against the normalized starless.
#
# Headless port of Cuiv's NarrowbandNormalization script (like VeraLux
# StarComposer below, that script is GUI-only with no CLI mode).
RUN_NARROWBAND_NORMALIZATION = True

NBN_LIGHTNESS           = "Ha"       # "Off" | "Original" | "Ha" | "SII" | "OIII"
NBN_BLEND_MODE          = "Mode 1"   # "Mode 1" | "Mode 2" | "Mode 3"
                                      # (HOO-palette-only setting; SHO/HSO
                                      # always have a real SII channel, so
                                      # this is unused for this pipeline --
                                      # kept here to document the intended
                                      # value if palette handling is ever
                                      # extended to HOO composites)
NBN_BLEND_AMOUNT        = 0.6        # 0.0 - 1.0 (HOO-palette-only, see above)
NBN_SCNR                = 0.9        # 0.0 - 1.0
NBN_OIII_BOOST          = 1.0        # 0.5 - 2.0
NBN_SII_BOOST           = 1.0        # 0.5 - 2.0
NBN_SHADOW_POINT        = 1.0        # 0.0 - 1.0
NBN_HIGHLIGHT_REDUCTION = 1.0        # 0.1 - 3.0
NBN_BRIGHTNESS          = 1.0        # 0.1 - 3.0

# ------------------------------------------------------------------------
# Step 7: VeraLux StarComposer recombination -- RUN_VERALUX_RECOMBINE
# ------------------------------------------------------------------------
# Only runs when RUN_STARXTERMINATOR (step 4) actually produced a
# stars_*.fits / stars_none_*.fits pair for this panel. Recombines them
# with a headless port of VeraLux StarComposer's own maths (same
# LogD-controlled rational tone-mapping core, "Hybrid Scalar/Vector"
# engine and Screen/Linear Add compositing), and OVERWRITES
# result_fits/*_stretched_result.fits with the recombined (stars back in)
# result.
#
# star_removal/stars_none_*.fits is left holding the plain STRETCHED
# starless (no stars recombined in) regardless of this setting -- so you
# can always run e.g. Narrowband Neutralisation on it manually and
# recombine yourself in the VeraLux GUI instead, whether or not this
# automatic step also ran.
RUN_VERALUX_RECOMBINE = True

VERALUX_STAR_INTENSITY_LOGD = 13.0     # "Star Intensity (Log D)", 1.0 - 21.0
VERALUX_PROFILE_HARDNESS    = 50.0    # "Profile Hardness (b)", 1.0 - 100.0
VERALUX_COLOR_GRIP          = 0.50    # "Color Grip (Blend)", 0.0 - 1.0 (0-100%)
VERALUX_SHADOW_CONVERGENCE  = 0.00    # "Shadow Conv (Hide Artifacts)", 0.0 - 3.0
# Adaptive Anchor computes its black point from THIS PANEL's own star
# pixels (5th percentile of the nonzero ones) before applying Log D --
# fine for a raw, undifferenced starmask that still carries residual sky
# glow, but stars_*.fits here is already a differential image (composite
# minus starless, from StarXTerminator's --stars), so its background
# should already sit near zero and there's little floor left to remove.
# Left on, two panels with identical Log D can still end up with visibly
# different star intensity, since each panel's anchor is computed
# independently and a higher anchor makes that panel's stars come out
# dimmer under the same curve. Off by default here for exactly that
# reason -- every panel then gets the same, absolute Log D curve.
VERALUX_ADAPTIVE_ANCHOR     = False   # "Adaptive Anchor"
# Used instead of the adaptive value when VERALUX_ADAPTIVE_ANCHOR is
# False: a fixed anchor, identical for every panel, if you still want a
# bit of floor suppression without the per-panel drift above. 0.0 (no
# subtraction at all) is the right starting point given stars_*.fits is
# already background-near-zero; raise it a little only if faint residual
# noise in the star layer is visibly showing through after the stretch.
VERALUX_MANUAL_ANCHOR       = 0.0
VERALUX_BLEND_MODE          = "screen"   # "screen" | "add" ("Screen (Safe)" /
                                          # "Linear Add (Physical)" in the GUI)

# Star Surgery (advanced) -- disabled by default, matching the GUI's own
# "Show Star Surgery" section left unchecked (all sliders default to 0):
VERALUX_CORE_REJECTION_LSR  = 0.0     # "Core Rejection (LSR)", 0.0 - 1.0 (0-100%)
VERALUX_REDUCTION           = 0.0     # "Reduction (Erosion)", 0.0 - 1.0 (0-100%)
VERALUX_OPTICAL_HEALING     = 0.0     # "Optical Healing (Halos)", 0.0 - 20.0

# Sensor profile used for luminance weighting -- must exactly match a key
# in VERALUX_SENSOR_PROFILES below (copied verbatim from VeraLux
# StarComposer's own SENSOR_PROFILES database).
VERALUX_SENSOR_PROFILE = "Sony IMX585 (ASI585) - STARVIS 2"

VERALUX_SENSOR_PROFILES = {
    "Rec.709 (Recommended)": (0.2126, 0.7152, 0.0722),
    "Sony IMX571 (ASI2600/QHY268)": (0.2944, 0.5021, 0.2035),
    "Sony IMX533 (ASI533)": (0.2910, 0.5072, 0.2018),
    "Sony IMX455 (ASI6200/QHY600)": (0.2987, 0.5001, 0.2013),
    "Sony IMX410 (ASI2400)": (0.3015, 0.5050, 0.1935),
    "Sony IMX269 (Altair/ToupTek)": (0.3040, 0.5010, 0.1950),
    "Sony IMX294 (ASI294)": (0.3068, 0.5008, 0.1925),
    "Sony IMX676 (ASI676)": (0.2880, 0.5100, 0.2020),
    "Sony IMX183 (ASI183)": (0.2967, 0.4983, 0.2050),
    "Sony IMX178 (ASI178)": (0.2346, 0.5206, 0.2448),
    "Sony IMX224 (ASI224)": (0.3402, 0.4765, 0.1833),
    "Sony IMX585 (ASI585) - STARVIS 2": (0.3431, 0.4822, 0.1747),
    "Sony IMX662 (ASI662) - STARVIS 2": (0.3430, 0.4821, 0.1749),
    "Sony IMX678 (ASI678) - STARVIS 2": (0.3426, 0.4825, 0.1750),
    "Sony IMX715 (ASI715) - STARVIS 2": (0.3410, 0.4840, 0.1750),
    "Sony IMX462 (ASI462)": (0.3333, 0.4866, 0.1801),
    "Sony IMX482 (ASI482)": (0.3150, 0.4950, 0.1900),
    "Panasonic MN34230 (ASI1600/QHY163)": (0.2650, 0.5250, 0.2100),
    "Canon EOS (Modern - 60D/600D/500D)": (0.2600, 0.5200, 0.2200),
    "Canon EOS (Legacy - 300D/40D/20D)": (0.2450, 0.5350, 0.2200),
    "Nikon DSLR (Modern - D5100/D7200)": (0.2650, 0.5100, 0.2250),
    "Nikon DSLR (Legacy - D3/D300/D90)": (0.2500, 0.5300, 0.2200),
    "Fujifilm X-Trans 5 HR": (0.2800, 0.5100, 0.2100),
    "ZWO Seestar S50": (0.3333, 0.4866, 0.1801),
    "ZWO Seestar S30": (0.2928, 0.5053, 0.2019),
    "Narrowband HOO": (0.5000, 0.2500, 0.2500),
    "Narrowband SHO": (0.3333, 0.3400, 0.3267),
}

# ------------------------------------------------------------------------
# Cross-panel star brightness harmonization -- RUN_STAR_HARMONIZE
# ------------------------------------------------------------------------
# Corrects for real differences in the linear star flux ITSELF between
# panels (different nights/sky conditions/exposure), which SPCC does not
# normalize -- SPCC only balances relative per-channel colour (its
# white-balance factors fix the reference channel's own scale at 1.0 and
# adjust the others relative to it), not the absolute brightness scale
# across panels/sessions. Left uncorrected, identical VERALUX_* settings
# (Log D especially) can still produce visibly different star intensity
# panel to panel, confirmed by comparing real stars_*.fits pairs: the same
# panel-to-panel percentile of star pixels differed by 3-4x even though
# the post-stretch background/nebula (already independently normalized by
# the statistical stretch's own per-panel target median) matched closely.
#
# This is computed once, across every panel queued in a given run, from
# each panel's own linear stars_*.fits, BEFORE the Log D stretch runs --
# see PASS 1 / PASS 2 in main() below. A linear gain only has a clean,
# predictable effect when applied before a strongly nonlinear curve like
# VeraLux's rational tone-map; applying an equivalent correction after
# stretching (e.g. Galactic_4_Tiff.py's RUN_HARMONIZE_PANELS) can't undo
# this properly, since bright and dim regions would already have been
# compressed disproportionately by the time a linear gain could reach them.
RUN_STAR_HARMONIZE = True

# Percentile of each panel's own nonzero star-layer pixels used as its
# "brightness level" for comparison. Deliberately NOT the max/near-max: in
# practice a panel's single brightest star is often already close to
# saturation regardless of overall exposure/sky differences, so it barely
# discriminates between panels; a slightly lower (but still high)
# percentile like 99.9 reflects the general star population instead.
STAR_HARMONIZE_PERCENTILE = 99.9

# The reference every panel is harmonized toward is the MEDIAN of that
# percentile across all star-removed panels in this run (consistent with
# how Galactic_4_Tiff.py's own harmonization picks its reference). Each
# panel's gain (reference / that panel's own level) is then clamped to
# [1/this, this], so one genuinely unusual panel can't get pushed to an
# extreme correction.
STAR_HARMONIZE_MAX_GAIN = 4.0
# ==============================================================================


def siril_log(siril, msg):
    safe = msg.encode("ascii", errors="replace").decode("ascii")
    if not safe.strip():
        safe = " "
    siril.log(safe)


def _quote_if_needed(arg):
    """
    Wrap an argument in double quotes if it contains whitespace, so Siril's
    command-line parser treats it as a single token instead of splitting on
    the internal space (e.g. Windows paths like 'D:\\...\\HIP 97434\\...').

    IMPORTANT: Siril only recognises a quoted token when the double-quote
    is the very FIRST character of that token. Quoting only the value in a
    '-key=value' style option (e.g. -out="C:\\a b") does NOT work -- Siril
    still splits on the space and leaves a stray quote character glued to
    the truncated path. The quote must wrap the ENTIRE token, prefix
    included (e.g. "-out=C:\\a b"), so it is the leading character.

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
    args = tuple(_quote_if_needed(a) for a in args)
    try:
        siril.cmd(*args)
        return True
    except Exception as exc:
        siril_log(siril, "  [WARNING] Command failed: " + " ".join(str(a) for a in args))
        siril_log(siril, "            " + str(exc))
        return False


def _build_spcc_args(composite_suffix):
    """
    Build the spcc command's argument list from the SPCC_* config, so the
    sensor, filters and (for narrowband) wavelengths/bandwidths are
    specified explicitly on every run instead of depending on whatever was
    last selected in Siril's SPCC dialog (which is what silently stays
    wrong indefinitely once set incorrectly once, since Siril remembers the
    last GUI selection across sessions).

    composite_suffix selects the mode: "_SHO" and "_HSO" run SPCC in
    Narrowband mode with the SII_*/HA_*/OIII_* wavelengths above mapped to
    R/G/B per that composite's own channel order (see the config block).
    Any other suffix (e.g. "_LRGB") uses the broadband sensor/filter
    settings instead. The sensor itself is passed either way, since its QE
    curve matters in both modes -- only the per-channel filter arguments
    are dropped for narrowband, since Siril ignores them there anyway and
    synthesises the NB filter curve from -rwl=/-rbw= etc. instead.
    """
    args = ["spcc"]
    is_narrowband = composite_suffix in ("_SHO", "_HSO")

    if SPCC_SENSOR_MODE == "osc":
        if SPCC_OSC_SENSOR:
            args.append("-oscsensor=" + SPCC_OSC_SENSOR)
        if not is_narrowband:
            if SPCC_OSC_FILTER:
                args.append("-oscfilter=" + SPCC_OSC_FILTER)
            if SPCC_OSC_LPF:
                args.append("-osclpf=" + SPCC_OSC_LPF)
    else:
        if SPCC_MONO_SENSOR:
            args.append("-monosensor=" + SPCC_MONO_SENSOR)
        if not is_narrowband:
            if SPCC_RFILTER:
                args.append("-rfilter=" + SPCC_RFILTER)
            if SPCC_GFILTER:
                args.append("-gfilter=" + SPCC_GFILTER)
            if SPCC_BFILTER:
                args.append("-bfilter=" + SPCC_BFILTER)

    if composite_suffix == "_SHO":
        args += [
            "-narrowband",
            "-rwl=" + str(SII_WAVELENGTH),  "-rbw=" + str(SII_BANDWIDTH),
            "-gwl=" + str(HA_WAVELENGTH),   "-gbw=" + str(HA_BANDWIDTH),
            "-bwl=" + str(OIII_WAVELENGTH), "-bbw=" + str(OIII_BANDWIDTH),
        ]
    elif composite_suffix == "_HSO":
        args += [
            "-narrowband",
            "-rwl=" + str(HA_WAVELENGTH),   "-rbw=" + str(HA_BANDWIDTH),
            "-gwl=" + str(SII_WAVELENGTH),  "-gbw=" + str(SII_BANDWIDTH),
            "-bwl=" + str(OIII_WAVELENGTH), "-bbw=" + str(OIII_BANDWIDTH),
        ]

    if SPCC_BGTOL:
        args.append("-bgtol=" + SPCC_BGTOL)
    if SPCC_WHITEREF:
        args.append("-whiteref=" + SPCC_WHITEREF)

    return args


def _build_bxt_args():
    """
    CLI arguments for `pyscript BlurXTerminator.py`, from the BXT_* config
    above. In Correct Only mode every other BXT_* option is pinned by the
    tool itself and ignored, so only --correct-only is sent.

    Flag names (--ansp, --nsd) match the live schema reported by
    `rc-astro bxt --json` at the time this was written -- if RC-Astro
    renames them again, check `pyscript BlurXTerminator.py --help` for the
    current names and update these two lines.
    """
    if BXT_CORRECT_ONLY:
        return ["--correct-only"]
    args = [
        "--ss", str(BXT_SHARPEN_STARS),
        "--ash", str(BXT_ADJUST_STAR_HALOS),
        "--sn", str(BXT_SHARPEN_NONSTELLAR),
    ]
    if BXT_AUTOMATIC_PSF:
        args.append("--ansp")
    else:
        args += ["--no-ansp", "--nsd", str(BXT_NONSTELLAR_RADIUS)]
    return args


def _build_nxt_args():
    """
    CLI arguments for `pyscript NoiseXTerminator.py`, from the NXT_* config
    above. See the NXT_COLOR_SEPARATION / NXT_FREQUENCY_SEPARATION comment
    in the config block: those two have no CLI flag and are not sent.
    """
    return ["--dn", str(NXT_DENOISE), "--it", str(NXT_ITERATIONS)]


def _build_sxt_args():
    """CLI arguments for `pyscript StarXTerminator.py`, from the
    STARXTERMINATOR_* config above. --stars is always passed so both the
    starless and stars-only images are produced."""
    args = ["--stars"]
    if STARXTERMINATOR_UNSCREEN:
        args.append("--unscreen")
    return args


# ---------------------------------------------------------------------------
# Statistical Stretch (headless port of Cyril Richard's Seti Astro
# Statistical Stretch PyQt script -- see the module docstring for that
# script). Only the pure numpy/astropy processing core is kept; the
# PyQt6 GUI, argparse CLI and Siril-image-lock plumbing are replaced by
# statistical_stretch() below, which reads/writes plain FITS files driven
# by the STAT_* config at the top of this file.
# ---------------------------------------------------------------------------

_LUMA_REC709  = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
_LUMA_REC601  = np.array([0.2990, 0.5870, 0.1140], dtype=np.float32)
_LUMA_REC2020 = np.array([0.2627, 0.6780, 0.0593], dtype=np.float32)

LUMA_PROFILES = {
    "rec709": {"weights": _LUMA_REC709, "category": "Standard"},
    "rec601": {"weights": _LUMA_REC601, "category": "Standard"},
    "rec2020": {"weights": _LUMA_REC2020, "category": "Standard"},
    "cie1931": {"weights": [0.176204, 0.812985, 0.0108109], "category": "CIE"},
    "average": {"weights": [0.3333, 0.3333, 0.3334], "category": "Simple"},
}


def resolve_luma_profile_weights(mode: str):
    key = str(mode).strip().lower()
    alias = {
        "rec.709": "rec709", "rec-709": "rec709", "rgb": "rec709", "k": "rec709",
        "rec.601": "rec601", "rec-601": "rec601",
        "rec.2020": "rec2020", "rec-2020": "rec2020",
    }
    key = alias.get(key, key)
    prof = LUMA_PROFILES.get(key)
    if not prof:
        return ("rec709", _LUMA_REC709, None)
    w = prof.get("weights", None)
    if w is not None:
        w = np.asarray(w, dtype=np.float32)
    return (key, w, None)


def compute_luminance(img: np.ndarray, method: str = "rec709",
                     weights: np.ndarray = None, noise_sigma=None) -> np.ndarray:
    f = np.clip(img, 0.0, 1.0).astype(np.float32, copy=False)
    if f.ndim == 2:
        return f
    if f.ndim != 3:
        raise ValueError("compute_luminance: expected 2-D or 3-D array.")

    H, W, C = f.shape
    if C == 1:
        return f[..., 0]

    if weights is not None:
        w = np.asarray(weights, dtype=np.float32)
        if w.size == 3:
            lum = np.tensordot(f[..., :3], w, axes=([2], [0]))
        else:
            lum = np.tensordot(f[..., :3], _LUMA_REC709, axes=([2], [0]))
    elif method == "rec601":
        lum = np.tensordot(f[..., :3], _LUMA_REC601, axes=([2],[0]))
    elif method == "rec2020":
        lum = np.tensordot(f[..., :3], _LUMA_REC2020, axes=([2],[0]))
    else:
        lum = np.tensordot(f[..., :3], _LUMA_REC709, axes=([2],[0]))

    return np.clip(lum.astype(np.float32, copy=False), 0.0, 1.0)


def recombine_luminance_linear_scale(target_rgb: np.ndarray, new_L: np.ndarray,
                                     weights: np.ndarray = _LUMA_REC709,
                                     eps: float = 1e-6, blend: float = 1.0,
                                     highlight_soft_knee: float = 0.0) -> np.ndarray:
    rgb = np.clip(target_rgb, 0.0, 1.0).astype(np.float32, copy=False)
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("Recombine Luminance requires an RGB target image.")

    H, W, _ = rgb.shape
    L = new_L.astype(np.float32)

    w = np.asarray(weights, dtype=np.float32)
    if w.shape != (3,):
        raise ValueError("weights must be length-3 for RGB recombine.")

    Y = rgb[..., 0]*w[0] + rgb[..., 1]*w[1] + rgb[..., 2]*w[2]
    s = L / (Y + eps)

    if highlight_soft_knee > 0.0:
        k = np.clip(highlight_soft_knee, 0.0, 1.0)
        s = s / (1.0 + k*(s - 1.0))

    out = rgb * s[..., None]
    out = np.clip(out, 0.0, 1.0)

    if 0.0 <= blend < 1.0:
        out = rgb*(1.0 - blend) + out*blend

    return out.astype(np.float32, copy=False)


def hdr_compress_highlights(x: np.ndarray, amount: float, knee: float = 0.75) -> np.ndarray:
    a = float(np.clip(amount, 0.0, 1.0))
    if a <= 0.0:
        return x.astype(np.float32, copy=False)
    k = float(np.clip(knee, 0.0, 0.99))
    y = x.astype(np.float32, copy=False)
    hi = y > k
    if not np.any(hi):
        return np.clip(y, 0.0, 1.0).astype(np.float32, copy=False)
    t = (y[hi] - k) / (1.0 - k)
    t = np.clip(t, 0.0, 1.0)
    m1 = 1.0 + 4.0 * a
    m1 = float(np.clip(m1, 1.0, 5.0))
    t2 = t * t
    t3 = t2 * t
    h10 = (t3 - 2.0 * t2 + t)
    h01 = (-2.0 * t3 + 3.0 * t2)
    h11 = (t3 - t2)
    f = h10 * 1.0 + h01 * 1.0 + h11 * m1
    y2 = y.copy()
    y2[hi] = k + (1.0 - k) * np.clip(f, 0.0, 1.0)
    return np.clip(y2, 0.0, 1.0).astype(np.float32, copy=False)


def hdr_compress_color_luminance(rgb: np.ndarray, amount: float, knee: float,
                                 luma_mode: str = "rec709") -> np.ndarray:
    a = float(np.clip(amount, 0.0, 1.0))
    if a <= 0.0:
        return rgb.astype(np.float32, copy=False)

    resolved_method, w, _ = resolve_luma_profile_weights(luma_mode)
    if w is not None and np.asarray(w).size == 3:
        rw = np.asarray(w, dtype=np.float32)
    else:
        if resolved_method == "rec601":
            rw = _LUMA_REC601
        elif resolved_method == "rec2020":
            rw = _LUMA_REC2020
        else:
            rw = _LUMA_REC709

    Y = compute_luminance(rgb, method=resolved_method, weights=rw)
    Yc = hdr_compress_highlights(Y, a, knee=float(knee))

    return recombine_luminance_linear_scale(rgb, Yc, weights=rw, blend=1.0,
                                           highlight_soft_knee=0.25)


def _sample_flat(x: np.ndarray, max_n: int = 400_000) -> np.ndarray:
    flat = np.asarray(x, np.float32).reshape(-1)
    n = flat.size
    if n <= max_n:
        return flat
    stride = max(1, n // max_n)
    return flat[::stride]


def _robust_sigma_lower_half_fast(x: np.ndarray, max_n: int = 400_000) -> float:
    s = _sample_flat(x, max_n=max_n)
    med = float(np.median(s))
    lo = s[s <= med]
    if lo.size < 16:
        mad = float(np.median(np.abs(s - med)))
    else:
        med_lo = float(np.median(lo))
        mad = float(np.median(np.abs(lo - med_lo)))
    return 1.4826 * mad


def _compute_blackpoint_sigma(img: np.ndarray, sigma: float) -> tuple:
    img = np.asarray(img, dtype=np.float32)
    med = float(np.median(img))
    sig = float(sigma)
    noise = _robust_sigma_lower_half_fast(img)
    bp = med - sig * noise
    mn = float(img.min())
    bp = max(mn, bp)
    bp = min(bp, 0.99)
    return float(bp), med


def _compute_blackpoint_sigma_per_channel(img: np.ndarray, sigma: float) -> np.ndarray:
    sig = float(sigma)
    bp = np.zeros(3, dtype=np.float32)
    for c in range(3):
        ch = img[..., c].astype(np.float32, copy=False)
        med = float(np.median(ch))
        noise = _robust_sigma_lower_half_fast(ch)
        b = med - sig * noise
        b = max(float(ch.min()), b)
        b = min(b, 0.99)
        bp[c] = b
    return bp


class StatisticalStretchProcessor:
    def __init__(self):
        pass

    def apply_curves_adjustment(self, image, target_median, curves_boost):
        if curves_boost <= 0.0:
            return np.clip(image, 0.0, 1.0).astype(np.float32)
        img = np.clip(image.astype(np.float32), 0.0, 1.0)
        tm = float(target_median)
        cb = float(curves_boost)
        p3x = 0.25 * (1.0 - tm) + tm
        p4x = 0.75 * (1.0 - tm) + tm
        p3y = p3x ** (1.0 - cb)
        p4y = (p4x ** (1.0 - cb)) ** (1.0 - cb)
        xvals = np.array([0.0, 0.5 * tm, tm, p3x, p4x, 1.0], dtype=np.float32)
        yvals = np.array([0.0, 0.5 * tm, tm, p3y, p4y, 1.0], dtype=np.float32)
        out = np.interp(img, xvals, yvals).astype(np.float32, copy=False)
        return np.clip(out, 0.0, 1.0)

    def stretch_mono_image(self, img, target_median, normalize=False, apply_curves=False,
                          curves_boost=0.0, blackpoint_sigma=5.0, no_black_clip=False,
                          hdr_compress=False, hdr_amount=0.0, hdr_knee=0.75):
        target_median = max(0.01, min(0.99, target_median))

        if no_black_clip:
            black_point = np.min(img)
            median_image = np.median(img)
        else:
            black_point, median_image = _compute_blackpoint_sigma(img, blackpoint_sigma)

        denom = max(1.0 - black_point, 1e-12)
        rescaled_image = (img - black_point) / denom
        median_rescaled = np.median(rescaled_image)

        num = (median_rescaled - 1) * target_median * rescaled_image
        den = median_rescaled * (target_median + rescaled_image - 1) - target_median * rescaled_image
        den = np.where(np.abs(den) < 1e-12, 1e-12, den)
        stretched_image = num / den

        if apply_curves:
            stretched_image = self.apply_curves_adjustment(stretched_image, target_median, curves_boost)

        if hdr_compress and hdr_amount > 0.0:
            stretched_image = hdr_compress_highlights(stretched_image, hdr_amount, knee=hdr_knee)

        if normalize:
            stretched_image = stretched_image / np.max(stretched_image)

        return np.clip(stretched_image, 0.0, 1.0).astype(np.float32)

    def stretch_color_image(self, img, target_median, linked=True, normalize=False,
                           apply_curves=False, curves_boost=0.0, blackpoint_sigma=5.0,
                           no_black_clip=False, hdr_compress=False, hdr_amount=0.0,
                           hdr_knee=0.75, luma_only=False, luma_mode="rec709",
                           luma_blend=1.0):
        target_median = max(0.01, min(0.99, target_median))
        sig = float(blackpoint_sigma)

        if img.ndim == 2 or (img.ndim == 3 and img.shape[2] == 1):
            mono = img.squeeze()
            mono_out = self.stretch_mono_image(
                mono, target_median, normalize, apply_curves, curves_boost,
                blackpoint_sigma, no_black_clip, hdr_compress, hdr_amount, hdr_knee
            )
            return np.stack([mono_out]*3, axis=-1)

        if luma_only:
            b = float(np.clip(luma_blend, 0.0, 1.0))

            # A) Normal linked RGB stretch
            if no_black_clip:
                bp = float(img.min())
                med_img = float(np.median(img))
            else:
                bp, med_img = _compute_blackpoint_sigma(img, sig)

            denom = max(1.0 - bp, 1e-12)
            med_rescaled = (med_img - bp) / denom

            rescaled_image = (img - bp) / denom
            median_image = np.median(rescaled_image)

            num = (median_image - 1) * target_median * rescaled_image
            den = median_image * (target_median + rescaled_image - 1) - target_median * rescaled_image
            den = np.where(np.abs(den) < 1e-12, 1e-12, den)
            linked_out = num / den

            if apply_curves:
                linked_out = self.apply_curves_adjustment(linked_out, target_median, curves_boost)

            if hdr_compress and hdr_amount > 0.0:
                linked_out = hdr_compress_color_luminance(linked_out, hdr_amount, hdr_knee, "rec709")

            if normalize:
                mx = float(linked_out.max())
                if mx > 0:
                    linked_out = linked_out / mx

            linked_out = np.clip(linked_out, 0.0, 1.0).astype(np.float32, copy=False)

            if b <= 0.0:
                return linked_out

            # B) Luma-only recombine stretch
            resolved_method, w, _profile_name = resolve_luma_profile_weights(luma_mode)

            L = compute_luminance(img, method=resolved_method, weights=w)

            Ls = self.stretch_mono_image(
                L, target_median, normalize=False, apply_curves=apply_curves,
                curves_boost=curves_boost, blackpoint_sigma=sig, no_black_clip=no_black_clip,
                hdr_compress=False, hdr_amount=0.0, hdr_knee=hdr_knee
            )

            if hdr_compress and hdr_amount > 0.0:
                Ls = hdr_compress_highlights(Ls, hdr_amount, knee=hdr_knee)

            if w is not None and np.asarray(w).size == 3:
                rw = np.asarray(w, dtype=np.float32)
                s = float(rw.sum())
                if s > 0:
                    rw = rw / s
            else:
                if resolved_method == "rec601":
                    rw = _LUMA_REC601
                elif resolved_method == "rec2020":
                    rw = _LUMA_REC2020
                else:
                    rw = _LUMA_REC709

            luma_out = recombine_luminance_linear_scale(
                img, Ls, weights=rw, blend=1.0, highlight_soft_knee=0.0
            )

            if normalize:
                mx = float(luma_out.max())
                if mx > 0:
                    luma_out = luma_out / mx

            luma_out = np.clip(luma_out, 0.0, 1.0).astype(np.float32, copy=False)

            out = (1.0 - b) * linked_out + b * luma_out
            return np.clip(out, 0.0, 1.0).astype(np.float32, copy=False)

        # Normal RGB mode
        if linked:
            if no_black_clip:
                black_point = np.min(img)
                combined_median = np.median(img)
            else:
                black_point, combined_median = _compute_blackpoint_sigma(img, blackpoint_sigma)

            rescaled_image = (img - black_point) / (1 - black_point)
            median_image = np.median(rescaled_image)

            num = (median_image - 1) * target_median * rescaled_image
            den = median_image * (target_median + rescaled_image - 1) - target_median * rescaled_image
            den = np.where(np.abs(den) < 1e-12, 1e-12, den)
            stretched_image = num / den
        else:
            stretched_image = np.zeros_like(img)
            for c in range(3):
                channel_data = img[..., c]
                if no_black_clip:
                    black_point = np.min(channel_data)
                    median_channel_data = np.median(channel_data)
                else:
                    black_point, median_channel_data = _compute_blackpoint_sigma(channel_data, blackpoint_sigma)

                rescaled_channel = (channel_data - black_point) / (1 - black_point)
                median_channel = np.median(rescaled_channel)

                num = (median_channel - 1) * target_median * rescaled_channel
                den = median_channel * (target_median + rescaled_channel - 1) - target_median * rescaled_channel
                den = np.where(np.abs(den) < 1e-12, 1e-12, den)
                stretched_channel = num / den

                stretched_image[..., c] = stretched_channel

        if apply_curves:
            stretched_image = self.apply_curves_adjustment(stretched_image, target_median, curves_boost)

        if hdr_compress and hdr_amount > 0.0:
            stretched_image = hdr_compress_color_luminance(stretched_image, hdr_amount, hdr_knee, "rec709")

        if normalize:
            stretched_image = stretched_image / np.max(stretched_image)

        return np.clip(stretched_image, 0.0, 1.0).astype(np.float32)


def _stretch_diagnostics(img, mono):
    """Short human-readable summary of the black point(s) actually used, for
    the per-panel log -- mirrors compute_clip_stats() from the original
    Statistical Stretch dialog, minus the pixel-count/clipping percentage
    (not meaningful here since STAT_NO_BLACK_CLIP only removes the sigma
    clip, it doesn't change what gets logged)."""
    sig = STAT_BLACKPOINT_SIGMA
    if mono:
        if STAT_NO_BLACK_CLIP:
            bp = float(np.min(img))
        else:
            bp, _ = _compute_blackpoint_sigma(img, sig)
        return "black point: {:.5f}".format(bp)
    if STAT_LINKED_STRETCH:
        if STAT_NO_BLACK_CLIP:
            bp = float(np.min(img))
        else:
            bp, _ = _compute_blackpoint_sigma(img, sig)
        return "black point (linked): {:.5f}".format(bp)
    if STAT_NO_BLACK_CLIP:
        bp3 = [float(img[..., c].min()) for c in range(3)]
    else:
        bp3 = list(_compute_blackpoint_sigma_per_channel(img, sig))
    return "black point R={:.5f} G={:.5f} B={:.5f}".format(*bp3)


def statistical_stretch(fits_path, out_path):
    """
    Apply the Statistical Stretch (see STAT_* config at the top of this
    file) to a linear FITS file and write the result to out_path.

    Returns (ok, info) -- info is a short diagnostic string for logging, or
    None on failure.
    """
    try:
        with _afits.open(str(fits_path)) as hdul:
            header = hdul[0].header.copy()
            data = hdul[0].data.astype(np.float32)

        mono = data.ndim == 2
        if mono:
            img = data
        else:
            # FITS/Siril planar CHW -> HWC, the layout the stretch maths
            # (ported unchanged from the Statistical Stretch dialog, which
            # receives Siril's own HWC pixel data) expects.
            img = np.moveaxis(data, 0, -1)

        max_val = float(np.nanmax(img)) if img.size else 1.0
        if max_val > 1.0:
            img = img / max_val

        info = _stretch_diagnostics(img, mono)

        processor = StatisticalStretchProcessor()
        if mono:
            out = processor.stretch_mono_image(
                img, STAT_TARGET_MEDIAN,
                normalize=STAT_NORMALIZE,
                apply_curves=STAT_APPLY_CURVES_BOOST,
                curves_boost=STAT_CURVES_BOOST_STRENGTH,
                blackpoint_sigma=STAT_BLACKPOINT_SIGMA,
                no_black_clip=STAT_NO_BLACK_CLIP,
                hdr_compress=STAT_HDR_COMPRESS,
                hdr_amount=STAT_HDR_AMOUNT,
                hdr_knee=STAT_HDR_KNEE,
            )
        else:
            out = processor.stretch_color_image(
                img, STAT_TARGET_MEDIAN,
                linked=STAT_LINKED_STRETCH,
                normalize=STAT_NORMALIZE,
                apply_curves=STAT_APPLY_CURVES_BOOST,
                curves_boost=STAT_CURVES_BOOST_STRENGTH,
                blackpoint_sigma=STAT_BLACKPOINT_SIGMA,
                no_black_clip=STAT_NO_BLACK_CLIP,
                hdr_compress=STAT_HDR_COMPRESS,
                hdr_amount=STAT_HDR_AMOUNT,
                hdr_knee=STAT_HDR_KNEE,
            )

        out_data = out if mono else np.moveaxis(out, -1, 0)

        out_hdu = _afits.PrimaryHDU(out_data.astype(np.float32), header=header)
        out_hdu.writeto(str(out_path), overwrite=True)
        return True, info

    except Exception:
        return False, None


# ---------------------------------------------------------------------------
# Narrowband Normalization (headless port of Yannick Dutertre / Cuiv's
# NarrowbandNormalization script -- itself a clean-room port of Bill
# Blanshan & Mike Cranfield's PixelMath process). That script is GUI-only
# too (no CLI/headless mode), so its pure numpy core -- process_image() and
# everything it calls -- is ported here unchanged and driven by the NBN_*
# config instead of sliders. process_image() itself works on (H, W, 3)
# arrays (channels-last), unlike the rest of this file's native (C, H, W)
# FITS layout, so narrowband_normalize() below converts on the way in/out.
# ---------------------------------------------------------------------------

_NBN_EPS = 1e-6

_NBN_PALETTE_SLOTS = {
    "HOO": {"Ha": 0, "OIII": 2},
    "SHO": {"SII": 0, "Ha": 1, "OIII": 2},
    "HSO": {"Ha": 0, "SII": 1, "OIII": 2},
    "HOS": {"Ha": 0, "OIII": 1, "SII": 2},
}


def _nbn_mtf(m, x):
    x = np.asarray(x, dtype=np.float32)
    if abs(m - 0.5) < 1e-9:
        return x.copy()
    denom = (2.0 * m - 1.0) * x - m
    denom = np.where(np.abs(denom) < _NBN_EPS, np.copysign(_NBN_EPS, denom), denom)
    return ((m - 1.0) * x) / denom


def _nbn_rescale(x, lo, hi):
    if abs(hi - lo) < _NBN_EPS:
        return np.clip(x - lo, 0.0, 1.0)
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def _nbn_normalize_range(data):
    data = np.asarray(data, dtype=np.float32)
    if data.size and float(np.nanmax(data)) > 1.5:
        return data / 65535.0
    return data


def _nbn_channel_stats(ch, blackpoint):
    mn = float(np.min(ch))
    med = float(np.median(ch))
    M = mn + blackpoint * (med - mn)
    mean = float(np.mean(ch, dtype=np.float64))
    adev = float(np.mean(np.abs(ch - mean), dtype=np.float64))
    E0 = adev / 1.2533 + mean - M
    return M, E0


def _nbn_boost_factor(a_target, a_ref, boost):
    denom = a_target - 2.0 * a_target * a_ref + a_ref
    if abs(denom) < 1e-9:
        denom = 1e-9
    return (a_target * (1.0 - a_ref) / denom) / boost


def _nbn_normalize_channel(ch, M_ch, strength):
    rescaled = _nbn_rescale(ch, M_ch, 1.0)
    stretched = _nbn_mtf(strength, rescaled)
    floor_part = np.minimum(ch, M_ch)
    out = 1.0 - (1.0 - stretched) * (1.0 - floor_part)
    return np.clip(out, 0.0, 1.0)


def _nbn_srgb_to_linear(c):
    c = np.clip(c, 0.0, None)
    return np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)


def _nbn_linear_to_srgb(c):
    c = np.clip(c, 0.0, None)
    return np.where(c > 0.0031308, 1.055 * (c ** (1.0 / 2.4)) - 0.055, 12.92 * c)


def _nbn_rgb_to_xyz(r, g, b):
    r1, g1, b1 = _nbn_srgb_to_linear(r), _nbn_srgb_to_linear(g), _nbn_srgb_to_linear(b)
    X = r1 * 0.4360747 + g1 * 0.3850649 + b1 * 0.1430804
    Y = r1 * 0.2225045 + g1 * 0.7168786 + b1 * 0.0606169
    Z = r1 * 0.0139322 + g1 * 0.0971045 + b1 * 0.7141733
    return X, Y, Z


def _nbn_f_lab(t):
    return np.where(t > 0.008856, np.cbrt(t), (7.787 * t) + 16.0 / 116.0)


def _nbn_f_lab_inv(t):
    return np.where(t > 0.206893, t ** 3, (t - 16.0 / 116.0) / 7.787)


def _nbn_xyz_to_lab(X, Y, Z):
    X1, Y1, Z1 = _nbn_f_lab(X), _nbn_f_lab(Y), _nbn_f_lab(Z)
    L = 116.0 * Y1 - 16.0
    a = 500.0 * (X1 - Y1)
    b = 200.0 * (Y1 - Z1)
    return L, a, b


def _nbn_xyz_to_rgb(X, Y, Z):
    R = X * 3.1338561 + Y * -1.6168667 + Z * -0.4906146
    G = X * -0.9787684 + Y * 1.9161415 + Z * 0.0334540
    B = X * 0.0719453 + Y * -0.2289914 + Z * 1.4052427
    return _nbn_linear_to_srgb(R), _nbn_linear_to_srgb(G), _nbn_linear_to_srgb(B)


def _nbn_cie_l_only(r, g, b):
    X, Y, Z = _nbn_rgb_to_xyz(r, g, b)
    L, _, _ = _nbn_xyz_to_lab(X, Y, Z)
    return (L + 16.0) / 116.0


def _nbn_synthetic_green(ha, oiii, mode, amount):
    amount = float(np.clip(amount, 0.0, 1.0))
    if mode == "Mode 1":
        g = amount * ha + (1.0 - amount) * oiii
    elif mode == "Mode 2":
        g = (np.clip(ha, 0, 1) ** amount) * (np.clip(oiii, 0, 1) ** (1.0 - amount))
    else:
        g = 1.0 - (1.0 - amount * ha) * (1.0 - (1.0 - amount) * oiii)
    return np.clip(g, 0.0, 1.0)


def _nbn_highlight_reduction(x, hl_reduction):
    hl_reduction = max(hl_reduction, 1e-3)
    m = 1.0 - 0.5 / hl_reduction
    term_a = _nbn_mtf(m, x) * x
    term_b = x * (1.0 - x)
    return term_a + term_b


def _nbn_brightness_stretch(x, brightness):
    brightness = max(brightness, 1e-3)
    return _nbn_mtf(1.0 / brightness * 0.5, x)


def _nbn_process_image(data, params):
    """data: (H, W, 3) float array in [0,1], R/G/B slots already arranged
    per the chosen palette's letter order. Returns an (H, W, 3) array."""
    palette = params["palette"]
    slots = _NBN_PALETTE_SLOTS[palette]
    data = np.asarray(data, dtype=np.float32)

    ha = data[:, :, slots["Ha"]]
    oiii = data[:, :, slots["OIII"]]
    sii = data[:, :, slots["SII"]] if "SII" in slots else None

    blackpoint = params["shadow_point"]

    M_ha, E0_ha = _nbn_channel_stats(ha, blackpoint)
    M_o, E0_o = _nbn_channel_stats(oiii, blackpoint)
    ref_denom = 1.0 - M_o
    if abs(ref_denom) < 1e-9:
        ref_denom = 1e-9
    A0_ha = E0_ha / ref_denom
    A0_o = E0_o / ref_denom

    E1 = _nbn_boost_factor(A0_o, A0_ha, params["oiii_boost"])
    oiii_norm = _nbn_normalize_channel(oiii, M_o, E1)

    if sii is not None:
        M_s, E0_s = _nbn_channel_stats(sii, blackpoint)
        A0_s = E0_s / ref_denom
        E4 = _nbn_boost_factor(A0_s, A0_ha, params["sii_boost"])
        sii_norm = _nbn_normalize_channel(sii, M_s, E4)
    else:
        sii_norm = None

    out = np.empty_like(data)
    out[:, :, slots["Ha"]] = ha
    out[:, :, slots["OIII"]] = oiii_norm

    if sii is not None:
        out[:, :, slots["SII"]] = sii_norm
    else:
        green = _nbn_synthetic_green(ha, oiii_norm, params["blend_mode"], params["blend_amount"])
        out[:, :, 1] = green

    if sii is not None:
        scnr_amt = float(np.clip(params["scnr"], 0.0, 1.0))
        if scnr_amt > 0.0:
            r_ch, g_ch, b_ch = out[:, :, 0], out[:, :, 1], out[:, :, 2]
            reduced = np.minimum(np.mean(np.stack([r_ch, b_ch]), axis=0), g_ch)
            out[:, :, 1] = (1.0 - scnr_amt) * g_ch + scnr_amt * reduced

    lightness = params["lightness"]
    if lightness != "Off":
        r, g, b = out[:, :, 0], out[:, :, 1], out[:, :, 2]
        X, Y, Z = _nbn_rgb_to_xyz(r, g, b)
        L, a, bb = _nbn_xyz_to_lab(X, Y, Z)
        del X, Y, Z, L

        if lightness == "Original":
            Y2 = _nbn_cie_l_only(data[:, :, 0], data[:, :, 1], data[:, :, 2])
        elif lightness == "Ha":
            Y2 = (ha + 0.16) / 1.16
        elif lightness == "SII" and sii is not None:
            Y2 = (sii + 0.16) / 1.16
        elif lightness == "SII" and sii is None:
            Y2 = (oiii + 0.16) / 1.16
        else:
            Y2 = (oiii + 0.16) / 1.16

        X2 = (a / 500.0) + Y2
        Z2 = Y2 - (bb / 200.0)
        del a, bb

        X3, Y3, Z3 = _nbn_f_lab_inv(X2), _nbn_f_lab_inv(Y2), _nbn_f_lab_inv(Z2)
        del X2, Y2, Z2

        r3, g3, b3 = _nbn_xyz_to_rgb(X3, Y3, Z3)
        del X3, Y3, Z3

        out[:, :, 0] = np.clip(r3, 0.0, 1.0)
        out[:, :, 1] = np.clip(g3, 0.0, 1.0)
        out[:, :, 2] = np.clip(b3, 0.0, 1.0)
        del r3, g3, b3

    out = _nbn_highlight_reduction(out, params["highlight_reduction"])
    out = _nbn_brightness_stretch(out, params["brightness"])
    out = _nbn_rescale(out, 0.0, 1.0)

    return out.astype(np.float32)


def narrowband_normalize(fits_path, out_path, palette):
    """
    Apply Narrowband Normalization (see NBN_* config above) to a stretched
    RGB FITS file whose R/G/B channels are already in the given palette's
    slot order (SHO: R=SII G=Ha B=OIII; HSO: R=Ha G=SII B=OIII -- matching
    how SPCC, step 1, calibrated the composite), writing the result to
    out_path. fits_path and out_path may be the same file.

    Returns (ok, info) -- info is a short diagnostic string for logging, or
    the error message on failure.
    """
    try:
        if palette not in _NBN_PALETTE_SLOTS:
            return False, "Unknown palette " + repr(palette)

        with _afits.open(str(fits_path)) as hdul:
            header = hdul[0].header.copy()
            data = hdul[0].data.astype(np.float32)   # copy, decoupled from the file

        if data.ndim != 3 or data.shape[0] != 3:
            return False, ("Narrowband Normalization needs a 3-channel image, got shape "
                           + str(data.shape))

        img_hwc = np.moveaxis(data, 0, -1)
        img_hwc = _nbn_normalize_range(img_hwc)
        img_hwc = np.clip(img_hwc, 0.0, 1.0)

        params = dict(
            palette=palette,
            lightness=NBN_LIGHTNESS,
            blend_mode=NBN_BLEND_MODE,
            blend_amount=NBN_BLEND_AMOUNT,
            scnr=NBN_SCNR,
            oiii_boost=NBN_OIII_BOOST,
            sii_boost=NBN_SII_BOOST,
            shadow_point=NBN_SHADOW_POINT,
            highlight_reduction=NBN_HIGHLIGHT_REDUCTION,
            brightness=NBN_BRIGHTNESS,
        )

        out_hwc = _nbn_process_image(img_hwc, params)
        out_chw = np.moveaxis(out_hwc, -1, 0)

        out_hdu = _afits.PrimaryHDU(out_chw.astype(np.float32), header=header)
        out_hdu.writeto(str(out_path), overwrite=True)

        info = ("palette={} lightness={} scnr={:.2f} oiii_boost={:.2f} sii_boost={:.2f} "
                "shadow={:.2f} hl_reduction={:.2f} brightness={:.2f}").format(
            palette, NBN_LIGHTNESS, NBN_SCNR, NBN_OIII_BOOST, NBN_SII_BOOST,
            NBN_SHADOW_POINT, NBN_HIGHLIGHT_REDUCTION, NBN_BRIGHTNESS)
        return True, info

    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# VeraLux StarComposer recombination (headless port of Riccardo Paterniti's
# VeraLux StarComposer script). VeraLux StarComposer.py itself is GUI-only
# (no CLI/headless mode), so instead of running it via pyscript, its own
# pure numpy/OpenCV recombination core -- VeraLuxCore + process_star_pipeline
# and the three "surgery" helpers -- is ported here unchanged and driven by
# the VERALUX_* config at the top of this file instead of sliders. Data
# stays in Siril/FITS's native channels-first (C, H, W) layout throughout,
# unlike the Statistical Stretch port above, since that's what VeraLux's own
# FITS loader (and this script's FITS files) already use.
# ---------------------------------------------------------------------------

def _veralux_normalize_input(img_data):
    input_dtype = img_data.dtype
    img_float = img_data.astype(np.float32)
    img_float = np.nan_to_num(img_float, nan=0.0, posinf=1.0, neginf=0.0)
    if np.issubdtype(input_dtype, np.integer):

        if input_dtype == np.uint8:
            return img_float / 255.0
        elif input_dtype == np.uint16:
            return img_float / 65535.0
        else:
            return img_float / float(np.iinfo(input_dtype).max)
    elif np.issubdtype(input_dtype, np.floating):
        current_max = np.max(img_data) if img_data.size else 0.0
        if current_max > 1.0 + 1e-5:
            if current_max <= 65535.0:
                return img_float / 65535.0
            return img_float / current_max
    return np.clip(img_float, 0.0, 1.0)


def _veralux_calculate_anchor_adaptive(data_norm, weights):
    stride = max(1, data_norm.size // 1000000)
    if data_norm.ndim == 3:
        r, g, b = weights
        L = r * data_norm[0] + g * data_norm[1] + b * data_norm[2]
        sample = L.flatten()[::stride]
    else:
        sample = data_norm.flatten()[::stride]

    valid = sample[sample > 0]
    if valid.size == 0:
        return 0.0

    sparsity = valid.size / sample.size
    if sparsity < 0.05:
        return 0.0

    return max(0.0, np.percentile(valid, 5.0))


def _veralux_extract_luminance(data_norm, anchor, weights):
    r_w, g_w, b_w = weights
    img_anchored = np.maximum(data_norm - anchor, 0.0)
    if data_norm.ndim == 3:
        L = (r_w * img_anchored[0] + g_w * img_anchored[1] + b_w * img_anchored[2])
    else:
        L = img_anchored
    return L, img_anchored


def _veralux_rational_tonemap(data, D, b):
    """VeraLux StarComposer's stretch core: a bounded rational tone-mapping
    curve (0 -> 0, 1 -> 1), controlled by D = 10**LogD and a toe-based
    Profile Hardness 'b'."""
    x = np.clip(data, 0.0, 1.0).astype(np.float32)
    D = float(max(D, 1e-12))
    b = float(max(b, 0.1))

    logD = math.log10(D)

    sf = (logD - 1.0) / 2.0
    sf = max(0.0, min(sf, 12.0))

    a = 3.0
    k = a ** sf

    u = (b - 50.0) / 50.0
    u = max(-1.5, min(1.5, u))
    s = u * u * u

    strength = 0.60
    t = 1.0 + strength * s
    t = max(t, 1e-3)

    eps_toe = 1e-9
    denom = x + t * (1.0 - x)
    denom = np.maximum(denom, eps_toe)
    x_n = x / denom
    x_n = np.clip(x_n, 0.0, 1.0)

    den = ((k - 1.0) * x_n) + 1.0
    y = (k * x_n) / den

    return np.clip(y, 0.0, 1.0).astype(np.float32)


def _veralux_apply_optical_healing(img_rgb, strength):
    if strength <= 0:
        return img_rgb
    img_cv = img_rgb.transpose(1, 2, 0)
    ycrcb = cv2.cvtColor(img_cv, cv2.COLOR_RGB2YCrCb)
    y, cr, cb = cv2.split(ycrcb)
    ksize = int(strength * 2) + 1
    if ksize % 2 == 0:
        ksize += 1
    cr = cv2.GaussianBlur(cr, (ksize, ksize), 0)
    cb = cv2.GaussianBlur(cb, (ksize, ksize), 0)
    merged = cv2.merge([y, cr, cb])
    rgb_heal = cv2.cvtColor(merged, cv2.COLOR_YCrCb2RGB)
    return rgb_heal.transpose(2, 0, 1)


def _veralux_apply_star_reduction(img_rgb, intensity):
    if intensity <= 0:
        return img_rgb
    k_size = 3 if intensity < 0.5 else 5
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
    img_hwc = img_rgb.transpose(1, 2, 0)
    eroded = cv2.erode(img_hwc, kernel, iterations=1)
    return (img_hwc * (1.0 - intensity) + eroded * intensity).transpose(2, 0, 1)


def _veralux_apply_large_structure_rejection(img_rgb, intensity):
    """Core Rejection (LSR): removes large blobs (e.g. galaxy cores) from
    the starmask via Difference of Gaussians, with a kernel size that
    scales with the image so it targets actual large-scale structures."""
    if intensity <= 0:
        return img_rgb

    h, w = img_rgb.shape[1], img_rgb.shape[2]
    k_size_val = int(min(h, w) / 15.0)
    if k_size_val % 2 == 0:
        k_size_val += 1
    if k_size_val < 3:
        k_size_val = 3

    img_hwc = img_rgb.transpose(1, 2, 0)
    low_pass = cv2.GaussianBlur(img_hwc, (k_size_val, k_size_val), 0)
    high_pass = np.maximum(img_hwc - low_pass, 0.0)
    result = img_hwc * (1.0 - intensity) + high_pass * intensity

    return result.transpose(2, 0, 1)


def _veralux_process_star_pipeline(starmask, D, b, grip, shadow, reduction,
                                   healing, lsr, weights, use_adaptive,
                                   manual_anchor=0.0, star_gain=1.0):
    """VeraLux StarComposer's Hybrid Scalar/Vector engine: stretches a
    linear starmask (C, H, W) into a developed star layer, ready to be
    composited onto a stretched starless image.

    manual_anchor is used in place of the adaptive (per-panel) anchor
    when use_adaptive is False -- see the VERALUX_ADAPTIVE_ANCHOR /
    VERALUX_MANUAL_ANCHOR config comments for why a fixed anchor, shared
    across every panel, gives more consistent star intensity than letting
    each panel compute its own.

    star_gain (see RUN_STAR_HARMONIZE) is a linear multiplier applied to
    the normalized star layer BEFORE the Log D curve -- the only point a
    simple multiplicative correction is meaningful, since it's applied
    before the strongly nonlinear tone-mapping rather than after it."""
    img = _veralux_normalize_input(starmask)
    if img.ndim == 2:
        img = np.array([img, img, img])

    img = np.clip(img * float(star_gain), 0.0, 1.0)

    # Transition smoothing (micro-blur)
    img_hwc = img.transpose(1, 2, 0)
    img_hwc = cv2.GaussianBlur(img_hwc, (0, 0), 0.5)
    img = img_hwc.transpose(2, 0, 1)

    anchor = _veralux_calculate_anchor_adaptive(img, weights) if use_adaptive else manual_anchor
    img_anchored = np.maximum(img - anchor, 0.0)

    D_val = 10.0 ** D

    # A. Scalar mapping (per-channel rational tone mapping)
    scalar = np.zeros_like(img)
    scalar[0] = _veralux_rational_tonemap(img_anchored[0], D_val, b)
    scalar[1] = _veralux_rational_tonemap(img_anchored[1], D_val, b)
    scalar[2] = _veralux_rational_tonemap(img_anchored[2], D_val, b)
    scalar = np.clip(scalar, 0.0, 1.0)

    # B. Vector mapping (luminance-driven, ratio-preserving)
    if grip > 0.001:
        L_anchored, _ = _veralux_extract_luminance(img, anchor, weights)
        L_str = _veralux_rational_tonemap(L_anchored, D_val, b)
        L_str = np.clip(L_str, 0.0, 1.0)

        epsilon = 1e-9
        L_safe = L_anchored + epsilon
        r_ratio = img_anchored[0] / L_safe
        g_ratio = img_anchored[1] / L_safe
        b_ratio = img_anchored[2] / L_safe

        vector = np.zeros_like(img)
        vector[0] = L_str * r_ratio
        vector[1] = L_str * g_ratio
        vector[2] = L_str * b_ratio
        vector = np.clip(vector, 0.0, 1.0)
    else:
        vector = scalar

    # Blending and Shadow Convergence
    if grip > 0.001:
        grip_map = np.full_like(scalar[0], grip)
        if shadow > 0.01:
            r_w, g_w, b_w = weights
            L_ref = (r_w * scalar[0]) + (g_w * scalar[1]) + (b_w * scalar[2])
            damping = np.power(L_ref, shadow)
            grip_map = grip_map * damping
        final = (vector * grip_map) + (scalar * (1.0 - grip_map))
    else:
        final = scalar

    final = np.clip(final, 0.0, 1.0).astype(np.float32)

    # Star Surgery
    if lsr > 0:
        final = _veralux_apply_large_structure_rejection(final, lsr)
    if healing > 0:
        final = _veralux_apply_optical_healing(final, healing)
    if reduction > 0:
        final = _veralux_apply_star_reduction(final, reduction)

    return final


def veralux_recombine(starmask_path, starless_path, out_path, star_gain=1.0):
    """
    Recombine a linear star mask (starmask_path, from StarXTerminator) with
    an already-stretched starless image (starless_path) using the VeraLux
    StarComposer maths above, driven by the VERALUX_* config. Writes the
    recombined RGB result to out_path (header copied from starless_path).

    star_gain (see RUN_STAR_HARMONIZE / compute_star_harmonization_gains())
    is a linear brightness correction for this panel's star layer,
    computed once across all panels in the run before any of them are
    stretched -- 1.0 (no change) if harmonization is off or wasn't
    computed for this panel.

    Returns (ok, info) -- info is a short diagnostic string for logging, or
    the error message on failure.
    """
    try:
        weights = VERALUX_SENSOR_PROFILES.get(VERALUX_SENSOR_PROFILE)
        if weights is None:
            return False, ("Unknown VERALUX_SENSOR_PROFILE " + repr(VERALUX_SENSOR_PROFILE)
                           + " -- check it matches a key in VERALUX_SENSOR_PROFILES exactly.")

        with _afits.open(str(starless_path)) as hdul:
            header = hdul[0].header.copy()
            starless = hdul[0].data.astype(np.float32)
        with _afits.open(str(starmask_path)) as hdul:
            starmask = hdul[0].data.astype(np.float32)

        starless = _veralux_normalize_input(starless)
        starmask = _veralux_normalize_input(starmask)

        if starless.ndim == 2:
            starless = np.stack([starless] * 3, axis=0)
        if starmask.ndim == 2:
            starmask = np.stack([starmask] * 3, axis=0)

        stars = _veralux_process_star_pipeline(
            starmask,
            D=VERALUX_STAR_INTENSITY_LOGD,
            b=VERALUX_PROFILE_HARDNESS,
            grip=VERALUX_COLOR_GRIP,
            shadow=VERALUX_SHADOW_CONVERGENCE,
            reduction=VERALUX_REDUCTION,
            healing=VERALUX_OPTICAL_HEALING,
            lsr=VERALUX_CORE_REJECTION_LSR,
            weights=weights,
            use_adaptive=VERALUX_ADAPTIVE_ANCHOR,
            manual_anchor=VERALUX_MANUAL_ANCHOR,
            star_gain=star_gain,
        )

        if starless.shape != stars.shape:
            h = min(starless.shape[1], stars.shape[1])
            w = min(starless.shape[2], stars.shape[2])
            starless = starless[:, :h, :w]
            stars = stars[:, :h, :w]

        if VERALUX_BLEND_MODE == "add":
            final = np.clip(starless + stars, 0.0, 1.0)
        else:
            final = 1.0 - (1.0 - starless) * (1.0 - stars)

        out_hdu = _afits.PrimaryHDU(final.astype(np.float32), header=header)
        out_hdu.writeto(str(out_path), overwrite=True)

        anchor_str = ("adaptive" if VERALUX_ADAPTIVE_ANCHOR
                     else "fixed={:.4f}".format(VERALUX_MANUAL_ANCHOR))
        info = ("LogD={:.2f} b={:.1f} grip={:.2f} shadow={:.2f} anchor={} "
                "star_gain={:.3f}x blend={} sensor={}".format(
            VERALUX_STAR_INTENSITY_LOGD, VERALUX_PROFILE_HARDNESS,
            VERALUX_COLOR_GRIP, VERALUX_SHADOW_CONVERGENCE, anchor_str,
            star_gain, VERALUX_BLEND_MODE, VERALUX_SENSOR_PROFILE))
        return True, info

    except Exception as exc:
        return False, str(exc)


def _star_layer_level(fits_path, percentile):
    """
    Robust brightness statistic for a linear star layer (stars_*.fits from
    StarXTerminator): the given percentile of its nonzero pixels, pooled
    across all channels together. See RUN_STAR_HARMONIZE's config comment
    for why a high-but-not-extreme percentile (not the max) is used.

    Returns the percentile value, or None if the file has no nonzero
    pixels or can't be read.
    """
    try:
        with _afits.open(str(fits_path)) as hdul:
            data = hdul[0].data.astype(np.float32)
        nz = data[data > 1e-9]
        if nz.size == 0:
            return None
        return float(np.percentile(nz, percentile))
    except Exception:
        return None


def compute_star_harmonization_gains(panel_states):
    """
    Compute a per-panel linear gain (see RUN_STAR_HARMONIZE) to bring
    every star-removed panel's stars_*.fits onto a common brightness
    scale, from the pass-1 results across the whole run (panel_states is
    the list of dicts returned by process_panel_part1()).

    Returns {key: gain} -- only for panels with star_removed=True and a
    readable star_level. A panel missing from the returned dict (star
    removal off/failed for it, harmonization off, or fewer than 2
    star-removed panels this run to compare against) should be treated as
    gain=1.0 by the caller.
    """
    levels = {}
    for st in panel_states:
        if not st.get("ok") or not st.get("star_removed"):
            continue
        lvl = st.get("star_level")
        if lvl is not None and lvl > 0:
            levels[st["key"]] = lvl

    if len(levels) < 2:
        return {}

    reference = float(np.median(list(levels.values())))
    gains = {}
    for key, lvl in levels.items():
        g = reference / lvl
        g = min(max(g, 1.0 / STAR_HARMONIZE_MAX_GAIN), STAR_HARMONIZE_MAX_GAIN)
        gains[key] = g
    return gains


def scan_all_panels(home_dir):
    """
    Scan home_dir/composites/ for GLAT*_(LRGB|HSO|SHO)[_NNNs].fits files
    and report the status of every one found -- "SKIP" if its result_fits/
    output already exists, "QUEUED" if it still needs processing.

    Matched via regex (not a simple suffix check) since the optional
    exposure postfix (e.g. "_1200s", written by Galactic_2_Composite.py)
    sits after "_LRGB"/"_HSO"/"_SHO". The postfix, if present, is carried
    forward into the result_fits output filename too.

    Returns a list of dicts: {prefix, composite_suffix, exposure_suffix,
    path, result_path, status}, sorted by filename -- printed in full
    before any processing starts, so it's clear what will run.
    """
    import re
    composites_dir = home_dir / "composites"
    if not composites_dir.is_dir():
        return []
    entries = []
    suf_pattern = "|".join(re.escape(s) for s in COMPOSITE_SUFFIXES)
    regex = re.compile(r"^(.*)(" + suf_pattern + r")(_\d+s)?$")
    for p in sorted(composites_dir.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in FITS_EXTENSIONS:
            continue
        if not p.stem.startswith("GLAT"):
            continue
        m = regex.match(p.stem)
        if not m:
            continue
        prefix, composite_suffix, exposure_suffix = m.group(1), m.group(2), m.group(3) or ""
        result_path = home_dir / "result_fits" / (
            prefix + composite_suffix + exposure_suffix + SUFFIX_RESULT + ".fits")
        status = "SKIP" if result_path.exists() else "QUEUED"
        entries.append({
            "prefix": prefix,
            "composite_suffix": composite_suffix,
            "exposure_suffix": exposure_suffix,
            "path": p,
            "result_path": result_path,
            "status": status,
        })
    return entries


def process_panel_part1(siril, prefix, composite_suffix, exposure_suffix, lrgb_path, home_dir):
    """
    PASS 1 (steps 1-4) for one plate-solved composite panel: colour
    calibration, RC-Astro sharpening/denoising, and (optionally) star
    removal. Split out from the stretch/recombine steps (process_panel_part2)
    so RUN_STAR_HARMONIZE can compare every panel's linear star layer
    against every other panel's BEFORE any of them go through the Log D
    stretch -- see that config comment for why this has to happen before
    stretching rather than after.

    Returns a dict describing the outcome (consumed by
    compute_star_harmonization_gains() and process_panel_part2()):
      key, prefix, cs, es, ok, result_out, cc_linear_path,
      stretch_input_path, star_removed, stars_path, stars_none_path,
      star_level
    ok=False means this panel failed pass 1 and pass 2 should skip it.
    """
    siril_log(siril, " ")
    siril_log(siril, "=" * 60)
    siril_log(siril, "Panel: " + prefix + "  [" + composite_suffix.strip("_") + "]"
              + (" " + exposure_suffix.strip("_") if exposure_suffix else "")
              + "  (pass 1/2)")
    siril_log(siril, "Input: " + lrgb_path.name)
    siril_log(siril, "=" * 60)

    process_dir = home_dir / "process"
    process_dir.mkdir(exist_ok=True)

    star_dir = home_dir / STAR_WORKING_DIR
    if RUN_STARXTERMINATOR:
        star_dir.mkdir(exist_ok=True)   # removed again at the end of main()
                                        # if it turns out to be empty

    # result_tiff/ is created by Galactic_4_Tiff.py, not here.
    result_fits_dir = home_dir / "result_fits"
    result_fits_dir.mkdir(exist_ok=True)

    cs = composite_suffix
    es = exposure_suffix   # e.g. "_1200s", or "" if unknown -- carried
                           # forward from the composite filename so total
                           # exposure stays visible at every pipeline stage
    key = prefix + cs + es
    result_out = result_fits_dir / (prefix + cs + es + SUFFIX_RESULT + ".fits")
    cc_linear_path = process_dir / (prefix + cs + es + SUFFIX_CC_LINEAR + ".fits")
    stars_path = star_dir / ("stars_" + prefix + cs + es + ".fits")
    stars_none_path = star_dir / ("stars_none_" + prefix + cs + es + ".fits")

    failed = {"key": key, "prefix": prefix, "cs": cs, "es": es,
              "ok": False, "result_out": result_out}

    cmd_safe(siril, "cd", str(home_dir))

    # ------------------------------------------------------------------
    # Steps 1-3: SPCC, then RC-Astro BlurXTerminator / NoiseXTerminator
    # (both optional via RUN_ flags), all operating on the loaded image.
    # ------------------------------------------------------------------
    if not cmd_safe(siril, "load", str(lrgb_path)):
        siril_log(siril, "  [ERROR] Cannot load " + lrgb_path.name)
        return failed

    if not RUN_SPCC:
        siril_log(siril, "  [1/7] Colour calibration SKIPPED (RUN_SPCC = False).")
        siril_log(siril, "  Assuming SPCC/Alchemy was already applied manually.")
    else:
        siril_log(siril, "  [1/7] Colour calibration (SPCC -> PCC fallback)...")

        if cs == "_SHO":
            siril_log(siril, "  SHO composite -- narrowband SPCC with "
                      "R=Sii({:g}nm) G=Ha({:g}nm) B=Oiii({:g}nm)".format(
                          SII_WAVELENGTH, HA_WAVELENGTH, OIII_WAVELENGTH))
        elif cs == "_HSO":
            siril_log(siril, "  HSO composite -- narrowband SPCC with "
                      "R=Ha({:g}nm) G=Sii({:g}nm) B=Oiii({:g}nm)".format(
                          HA_WAVELENGTH, SII_WAVELENGTH, OIII_WAVELENGTH))
        else:
            siril_log(siril, "  Wideband mode -- SPCC with " + SPCC_SENSOR_MODE
                      + " sensor "
                      + (SPCC_MONO_SENSOR if SPCC_SENSOR_MODE != "osc" else SPCC_OSC_SENSOR))

        spcc_args = _build_spcc_args(cs)
        # Log the exact arguments sent, since Siril's own "Running command:
        # spcc" line doesn't echo them and its post-hoc "will use ..."
        # confirmation message can be misleading in narrowband mode.
        siril_log(siril, "  spcc " + " ".join(spcc_args[1:]))
        cc_ok = cmd_safe(siril, *spcc_args)

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

    if RUN_BLURXTERMINATOR:
        siril_log(siril, "  [2/7] RC-Astro BlurXTerminator...")
        bxt_ok = cmd_safe(siril, "pyscript", "BlurXTerminator.py", *_build_bxt_args())
        if not bxt_ok:
            siril_log(siril, "  [WARNING] BlurXTerminator failed -- continuing without it.")
    else:
        siril_log(siril, "  [2/7] BlurXTerminator skipped (RUN_BLURXTERMINATOR = False).")

    if RUN_NOISEXTERMINATOR:
        siril_log(siril, "  [3/7] RC-Astro NoiseXTerminator...")
        nxt_ok = cmd_safe(siril, "pyscript", "NoiseXTerminator.py", *_build_nxt_args())
        if not nxt_ok:
            siril_log(siril, "  [WARNING] NoiseXTerminator failed -- continuing without it.")
    else:
        siril_log(siril, "  [3/7] NoiseXTerminator skipped (RUN_NOISEXTERMINATOR = False).")

    if not cmd_safe(siril, "save", str(cc_linear_path)):
        siril_log(siril, "  [ERROR] Cannot save cc_linear.")
        return failed

    # ------------------------------------------------------------------
    # Step 4: RC-Astro StarXTerminator (optional) -- splits the composite
    # into a starless image and a stars-only image, saved into
    # star_removal/ so they can be recombined with VeraLux StarComposer
    # once the stretch (step 5, in pass 2) is done. Also where each
    # panel's star-brightness level gets measured for RUN_STAR_HARMONIZE,
    # since that has to happen before any panel is stretched.
    # ------------------------------------------------------------------
    stretch_input_path = cc_linear_path
    star_removed = False
    star_level = None
    if RUN_STARXTERMINATOR:
        siril_log(siril, "  [4/7] RC-Astro StarXTerminator...")
        sxt_ok = cmd_safe(siril, "pyscript", "StarXTerminator.py", *_build_sxt_args())
        if not sxt_ok:
            siril_log(siril, "  [WARNING] StarXTerminator failed -- stretching the "
                      "composite instead.")
        else:
            # StarXTerminator.py saves its stars-only sidecar into the
            # working directory as "stars_<loaded-image-name>.<ext>" (ext
            # per Siril's own configured FITS extension). Find it by
            # pattern rather than assuming the exact extension, and MOVE
            # (not copy) it into star_dir under this script's own naming --
            # copying alone left the original sidecar behind as a scrap
            # file in home_dir.
            matches = sorted(home_dir.glob("stars_" + cc_linear_path.stem + ".*"))
            if matches:
                shutil.move(str(matches[0]), str(stars_path))
                siril_log(siril, "  Stars image saved: " + stars_path.name)
            else:
                siril_log(siril, "  [WARNING] Could not find the StarXTerminator "
                          "stars sidecar file; " + stars_path.name + " not written.")
            # The loaded image is now the starless result -- save it as the
            # input to the stretch step.
            if cmd_safe(siril, "save", str(stars_none_path)):
                stretch_input_path = stars_none_path
                star_removed = True
                siril_log(siril, "  Starless image saved: " + stars_none_path.name)
                if matches:
                    star_level = _star_layer_level(stars_path, STAR_HARMONIZE_PERCENTILE)
                    if star_level is not None:
                        siril_log(siril, "  Star layer level (p{:.1f} of nonzero px): "
                                  "{:.6f}".format(STAR_HARMONIZE_PERCENTILE, star_level))
            else:
                siril_log(siril, "  [WARNING] Could not save the starless image; "
                          "stretching the composite instead.")
    else:
        siril_log(siril, "  [4/7] StarXTerminator skipped (RUN_STARXTERMINATOR = False).")

    cmd_safe(siril, "cd", str(home_dir))

    return {
        "key": key, "prefix": prefix, "cs": cs, "es": es, "ok": True,
        "result_out": result_out, "cc_linear_path": cc_linear_path,
        "stretch_input_path": stretch_input_path, "star_removed": star_removed,
        "stars_path": stars_path, "stars_none_path": stars_none_path,
        "star_level": star_level,
    }


def process_panel_part2(siril, state, star_gain, home_dir):
    """
    PASS 2 (steps 5-7) for one panel already run through
    process_panel_part1(): statistical stretch, Narrowband Normalization,
    and VeraLux recombination. star_gain (see RUN_STAR_HARMONIZE /
    compute_star_harmonization_gains()) is applied to this panel's linear
    star layer before VeraLux's Log D curve, if it had its stars removed;
    pass 1.0 when harmonization is off or wasn't computed for this panel.
    """
    prefix = state["prefix"]
    cs = state["cs"]
    result_out = state["result_out"]
    stretch_input_path = state["stretch_input_path"]
    star_removed = state["star_removed"]
    stars_path = state["stars_path"]
    stars_none_path = state["stars_none_path"]

    siril_log(siril, " ")
    siril_log(siril, "  Panel " + prefix + "  (pass 2/2)")

    # ------------------------------------------------------------------
    # Step 5: Statistical stretch (see STAT_* config above), then save.
    # ------------------------------------------------------------------
    siril_log(siril, "  [5/7] Applying statistical stretch...")
    ok, info = statistical_stretch(stretch_input_path, result_out)
    if not ok:
        siril_log(siril, "  [ERROR] Stretch failed.")
        return False

    siril_log(siril, "  " + (info or ""))
    siril_log(siril, "  Stretched from: " + stretch_input_path.name)
    siril_log(siril, "  Saved: " + result_out.name)

    # If StarXTerminator ran, keep star_removal/ self-contained: stars_none_
    # above was saved BEFORE the stretch (still linear), so overwrite it with
    # the actual stretched result too -- it (and stars_*.fits alongside it,
    # untouched, still linear) then stay ready for manual work at any time
    # (e.g. Narrowband Neutralisation then a manual VeraLux recombine),
    # regardless of whether steps 6-7 below also run automatically.
    final_view_path = result_out
    if star_removed:
        try:
            shutil.copyfile(str(result_out), str(stars_none_path))
            siril_log(siril, "  Updated with stretched result: " + stars_none_path.name)
            final_view_path = stars_none_path
        except Exception as exc:
            siril_log(siril, "  [WARNING] Could not update " + stars_none_path.name
                      + " with the stretched result: " + str(exc))

    # ------------------------------------------------------------------
    # Step 6: Narrowband Normalization (optional, _SHO/_HSO composites
    # only -- see NBN_* config above). Applied to result_out, and to
    # star_removal/stars_none_*.fits too if StarXTerminator ran, so step 7
    # (VeraLux recombination) below still composites against the
    # normalized starless rather than the pre-normalization one.
    # ------------------------------------------------------------------
    if RUN_NARROWBAND_NORMALIZATION and cs in ("_SHO", "_HSO"):
        palette = cs.strip("_")
        siril_log(siril, "  [6/7] Narrowband Normalization (" + palette + ")...")
        nbn_ok, nbn_info = narrowband_normalize(result_out, result_out, palette)
        if not nbn_ok:
            siril_log(siril, "  [WARNING] Narrowband Normalization failed: " + str(nbn_info))
        else:
            siril_log(siril, "  " + nbn_info)
            if star_removed:
                nbn_ok2, nbn_info2 = narrowband_normalize(
                    stars_none_path, stars_none_path, palette)
                if not nbn_ok2:
                    siril_log(siril, "  [WARNING] Could not apply Narrowband Normalization to "
                              + stars_none_path.name + ": " + str(nbn_info2))
    elif RUN_NARROWBAND_NORMALIZATION:
        siril_log(siril, "  [6/7] Narrowband Normalization skipped (not an SHO/HSO composite).")
    else:
        siril_log(siril, "  [6/7] Narrowband Normalization skipped "
                  "(RUN_NARROWBAND_NORMALIZATION = False).")

    # ------------------------------------------------------------------
    # Step 7: VeraLux StarComposer recombination (optional, only when step
    # 4 produced a stars_*/stars_none_* pair for this panel). OVERWRITES
    # result_out with the recombined result; stars_*.fits and
    # stars_none_*.fits above are left exactly as they were, untouched by
    # this step.
    # ------------------------------------------------------------------
    if star_removed and RUN_VERALUX_RECOMBINE:
        siril_log(siril, "  [7/7] VeraLux StarComposer recombination...")
        if RUN_STAR_HARMONIZE and abs(star_gain - 1.0) > 1e-6:
            siril_log(siril, "  Star brightness harmonization gain: {:.3f}x".format(star_gain))
        vlx_ok, vlx_info = veralux_recombine(stars_path, stars_none_path, result_out,
                                             star_gain=star_gain)
        if not vlx_ok:
            siril_log(siril, "  [WARNING] VeraLux recombination failed: " + str(vlx_info)
                      + " -- result_fits/ keeps the starless-only stretch.")
        else:
            siril_log(siril, "  " + vlx_info)
            siril_log(siril, "  Recombined result saved: " + result_out.name)
            final_view_path = result_out
    elif star_removed:
        siril_log(siril, "  [7/7] VeraLux recombination skipped (RUN_VERALUX_RECOMBINE = False).")
    else:
        siril_log(siril, "  [7/7] VeraLux recombination skipped (no star removal for this panel).")

    siril_log(siril, "  Next: run Galactic_4_Tiff.py to export TIFFs for stitching.")

    # statistical_stretch()/veralux_recombine() write result_out directly via
    # astropy, bypassing Siril's own loaded image entirely -- so without
    # this, the viewer would be left showing stretch_input_path or
    # stars_none_path rather than the actual final result. Load it back in
    # so what's on screen matches what was just saved.
    if not cmd_safe(siril, "load", str(final_view_path)):
        siril_log(siril, "  [WARNING] Could not load the final result back into Siril.")

    cmd_safe(siril, "cd", str(home_dir))
    siril_log(siril, "  Panel " + prefix + " complete.")
    return True


def main():
    siril = s.SirilInterface()
    try:
        siril.connect()
        siril_log(siril, "Galactic_3_Stretch v6.0.0 connected.")
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

        all_entries = scan_all_panels(home_dir)

        if not all_entries:
            siril_log(siril, "No plate-solved LRGB panels found.")
            siril_log(siril, "Expected: GLAT*_LRGB.fits files in " + str(home_dir / "composites"))
            siril_log(siril, "Plate-solve your LRGB files with ASTAP first.")
            siril.disconnect()
            return

        siril_log(siril, "Found " + str(len(all_entries)) + " composite panel(s):")
        for e in all_entries:
            siril_log(siril, "  [{}] {}".format(e["status"], e["path"].name))

        panels = [(e["prefix"], e["composite_suffix"], e["exposure_suffix"], e["path"])
                  for e in all_entries if e["status"] == "QUEUED"]
        n_skip = len(all_entries) - len(panels)

        if not panels:
            siril_log(siril, " ")
            siril_log(siril, "All panels already have a result_fits/*_stretched_result.fits.")
            siril_log(siril, "Delete the ones you want reprocessed and re-run.")
            siril.disconnect()
            return

        siril_log(siril, " ")
        siril_log(siril, str(len(panels)) + " panel(s) queued to process, "
                  + str(n_skip) + " skipped (already done):")
        for prefix, composite_suffix, exposure_suffix, p in panels:
            siril_log(siril, "  " + p.name)

        # ------------------------------------------------------------------
        # PASS 1/2: colour calibration, sharpening/denoising, star removal
        # (steps 1-4) for every queued panel. Split from pass 2 so every
        # panel's linear star layer exists before RUN_STAR_HARMONIZE
        # compares them -- see that config comment. With
        # RUN_STARXTERMINATOR = False this pass just runs steps 1-3 for
        # every panel as before; no star layers exist, so harmonization
        # below is a no-op and pass 2 proceeds exactly as it always has.
        # ------------------------------------------------------------------
        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "PASS 1/2: colour calibration, sharpening/denoising, star removal")
        siril_log(siril, "=" * 60)

        pass1_states = []
        for prefix, composite_suffix, exposure_suffix, lrgb_path in panels:
            pass1_states.append(process_panel_part1(
                siril, prefix, composite_suffix, exposure_suffix, lrgb_path, home_dir))

        # ------------------------------------------------------------------
        # Cross-panel star brightness harmonization -- see RUN_STAR_HARMONIZE
        # config comment. Computed once here, from every panel's star layer,
        # before any of them are stretched.
        # ------------------------------------------------------------------
        gains = {}
        if RUN_STARXTERMINATOR and RUN_STAR_HARMONIZE:
            gains = compute_star_harmonization_gains(pass1_states)
            siril_log(siril, " ")
            if gains:
                siril_log(siril, "Star brightness harmonization (p{:.1f} percentile, "
                          "reference = median across panels):".format(STAR_HARMONIZE_PERCENTILE))
                for st in pass1_states:
                    if st["key"] in gains:
                        siril_log(siril, "  " + st["key"] + "  gain={:.3f}x".format(gains[st["key"]]))
            else:
                siril_log(siril, "Star brightness harmonization: nothing to harmonize this run "
                          "(need at least 2 star-removed panels with a readable level).")

        # ------------------------------------------------------------------
        # PASS 2/2: statistical stretch, Narrowband Normalization, VeraLux
        # recombination (steps 5-7) for every panel pass 1 succeeded on.
        # ------------------------------------------------------------------
        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "PASS 2/2: stretch, narrowband normalization, star recombination")
        siril_log(siril, "=" * 60)

        ok = fail = 0
        results = []
        for state in pass1_states:
            label = state["prefix"] + state["cs"] + state["es"]
            if not state["ok"]:
                fail += 1
                results.append((label, "FAIL"))
                continue
            gain = gains.get(state["key"], 1.0)
            if process_panel_part2(siril, state, gain, home_dir):
                ok += 1
                results.append((label, "OK"))
            else:
                fail += 1
                results.append((label, "FAIL"))

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
                  + "   SKIP: " + str(n_skip)
                  + "   TOTAL: " + str(len(all_entries)))
        siril_log(siril, "  Output: result_fits/GLAT*_stretched_result.fits")
        if RUN_STARXTERMINATOR:
            siril_log(siril, "  Stars for recombination: " + STAR_WORKING_DIR + "/stars_*.fits")
        else:
            # star_removal/ is only ever created when RUN_STARXTERMINATOR is
            # True; this just clears out a leftover empty one from a
            # previous run where it was enabled. If it's non-empty (star
            # files actually present), it's left alone.
            try:
                (home_dir / STAR_WORKING_DIR).rmdir()
            except OSError:
                pass
        siril_log(siril, "  Next: make any final adjustments, then run Galactic_4_Tiff.py")
        siril_log(siril, "=" * 60)

    except Exception as exc:
        siril_log(siril, "Unhandled error: " + str(exc))
        traceback.print_exc()
    finally:
        try:
            home_dir = Path(siril.get_siril_wd())
            siril.cmd("cd", _quote_if_needed(str(home_dir)))
        except Exception:
            pass
        siril.disconnect()


main()