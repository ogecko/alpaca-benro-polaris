# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_3_Stretch.py
# Version: 3.0.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# ==============================================================================
# OVERVIEW
# ==============================================================================
# Processes each plate-solved composite from composites/ into a final
# stretched result, ready for Galactic_4_Tiff.py:
#
#   1. SPCC colour calibration                (optional, RUN_SPCC)
#   2. RC-Astro BlurXTerminator                (optional, RUN_BLURXTERMINATOR)
#   3. RC-Astro NoiseXTerminator               (optional, RUN_NOISEXTERMINATOR)
#   4. RC-Astro StarXTerminator                (optional, RUN_STARXTERMINATOR)
#      -- splits the composite into stars_*.fits / stars_none_*.fits in
#      star_removal/, ready to be recombined with VeraLux StarComposer
#      once the stretch below is done.
#   5. Statistical stretch (see STAT_* below), applied to stars_none_*.fits
#      if StarXTerminator ran, otherwise to the composite itself, then
#      saved to result_fits/GLAT*_stretched_result.fits
#
# Steps 2-4 run via Siril's `pyscript` command, which drives RC-Astro's
# stand-alone command-line tool through the BlurXTerminator.py /
# NoiseXTerminator.py / StarXTerminator.py scripts. RC-Astro is a separate,
# licensed product from https://www.rc-astro.com and must be installed and
# licensed independently; these scripts must be discoverable by Siril's
# `pyscript` command (working directory, user script paths, or the
# siril-scripts repo).
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
# skipped. Delete that file to reprocess a panel.

import sirilpy as s

s.ensure_installed("numpy", "astropy")

import shutil
import traceback
from pathlib import Path

import numpy as np
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


def process_panel(siril, prefix, composite_suffix, exposure_suffix, lrgb_path, home_dir):
    """Run steps 1-5 for one plate-solved composite panel."""
    siril_log(siril, " ")
    siril_log(siril, "=" * 60)
    siril_log(siril, "Panel: " + prefix + "  [" + composite_suffix.strip("_") + "]"
              + (" " + exposure_suffix.strip("_") if exposure_suffix else ""))
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
    result_out = result_fits_dir / (prefix + cs + es + SUFFIX_RESULT + ".fits")
    cc_linear_path = process_dir / (prefix + cs + es + SUFFIX_CC_LINEAR + ".fits")
    stars_path = star_dir / ("stars_" + prefix + cs + es + ".fits")
    stars_none_path = star_dir / ("stars_none_" + prefix + cs + es + ".fits")

    cmd_safe(siril, "cd", str(home_dir))

    # ------------------------------------------------------------------
    # Steps 1-3: SPCC, then RC-Astro BlurXTerminator / NoiseXTerminator
    # (both optional via RUN_ flags), all operating on the loaded image.
    # ------------------------------------------------------------------
    if not cmd_safe(siril, "load", str(lrgb_path)):
        siril_log(siril, "  [ERROR] Cannot load " + lrgb_path.name)
        return False

    if not RUN_SPCC:
        siril_log(siril, "  [1/5] Colour calibration SKIPPED (RUN_SPCC = False).")
        siril_log(siril, "  Assuming SPCC/Alchemy was already applied manually.")
    else:
        siril_log(siril, "  [1/5] Colour calibration (SPCC -> PCC fallback)...")

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
        siril_log(siril, "  [2/5] RC-Astro BlurXTerminator...")
        bxt_ok = cmd_safe(siril, "pyscript", "BlurXTerminator.py", *_build_bxt_args())
        if not bxt_ok:
            siril_log(siril, "  [WARNING] BlurXTerminator failed -- continuing without it.")
    else:
        siril_log(siril, "  [2/5] BlurXTerminator skipped (RUN_BLURXTERMINATOR = False).")

    if RUN_NOISEXTERMINATOR:
        siril_log(siril, "  [3/5] RC-Astro NoiseXTerminator...")
        nxt_ok = cmd_safe(siril, "pyscript", "NoiseXTerminator.py", *_build_nxt_args())
        if not nxt_ok:
            siril_log(siril, "  [WARNING] NoiseXTerminator failed -- continuing without it.")
    else:
        siril_log(siril, "  [3/5] NoiseXTerminator skipped (RUN_NOISEXTERMINATOR = False).")

    if not cmd_safe(siril, "save", str(cc_linear_path)):
        siril_log(siril, "  [ERROR] Cannot save cc_linear.")
        return False

    # ------------------------------------------------------------------
    # Step 4: RC-Astro StarXTerminator (optional) -- splits the composite
    # into a starless image and a stars-only image, saved into
    # star_removal/ so they can be recombined with VeraLux StarComposer
    # once the stretch (step 5) is done.
    # ------------------------------------------------------------------
    stretch_input_path = cc_linear_path
    star_removed = False
    if RUN_STARXTERMINATOR:
        siril_log(siril, "  [4/5] RC-Astro StarXTerminator...")
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
            else:
                siril_log(siril, "  [WARNING] Could not save the starless image; "
                          "stretching the composite instead.")
    else:
        siril_log(siril, "  [4/5] StarXTerminator skipped (RUN_STARXTERMINATOR = False).")

    # ------------------------------------------------------------------
    # Step 5: Statistical stretch (see STAT_* config above), then save.
    # ------------------------------------------------------------------
    siril_log(siril, "  [5/5] Applying statistical stretch...")
    ok, info = statistical_stretch(stretch_input_path, result_out)
    if not ok:
        siril_log(siril, "  [ERROR] Stretch failed.")
        return False

    siril_log(siril, "  " + (info or ""))
    siril_log(siril, "  Stretched from: " + stretch_input_path.name)
    siril_log(siril, "  Saved: " + result_out.name)
    siril_log(siril, "  Next: run Galactic_4_Tiff.py to export TIFFs for stitching.")

    # If StarXTerminator ran, keep star_removal/ self-contained and ready
    # for recombination with VeraLux StarComposer: stars_none_*.fits above
    # was saved BEFORE the stretch (still linear), so overwrite it with the
    # actual stretched result too -- it and stars_*.fits alongside it then
    # both reflect the finished, stretched state. The viewer is then left
    # showing this file rather than the result_fits/ copy.
    final_view_path = result_out
    if star_removed:
        try:
            shutil.copyfile(str(result_out), str(stars_none_path))
            siril_log(siril, "  Updated with stretched result: " + stars_none_path.name)
            final_view_path = stars_none_path
        except Exception as exc:
            siril_log(siril, "  [WARNING] Could not update " + stars_none_path.name
                      + " with the stretched result: " + str(exc))

    # statistical_stretch() writes result_out directly via astropy, bypassing
    # Siril's own loaded image entirely -- so without this, the viewer would
    # be left showing stretch_input_path (cc_linear/stars_none, still
    # linear) rather than the actual stretched result. Load it back in so
    # what's on screen matches what was just saved.
    if not cmd_safe(siril, "load", str(final_view_path)):
        siril_log(siril, "  [WARNING] Could not load the stretched result back into Siril.")

    cmd_safe(siril, "cd", str(home_dir))
    siril_log(siril, "  Panel " + prefix + " complete.")
    return True


def main():
    siril = s.SirilInterface()
    try:
        siril.connect()
        siril_log(siril, "Galactic_3_Stretch v3.0.0 connected.")
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

        ok = fail = 0
        results = []
        for prefix, composite_suffix, exposure_suffix, lrgb_path in panels:
            if process_panel(siril, prefix, composite_suffix, exposure_suffix, lrgb_path, home_dir):
                ok += 1
                results.append((prefix + composite_suffix + exposure_suffix, "OK"))
            else:
                fail += 1
                results.append((prefix + composite_suffix + exposure_suffix, "FAIL"))

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