# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_3_Stretch.py
# Version: 2.0.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# Description
# -----------
# Processes plate-solved GLAT*_(LRGB|SHO|HSO).fits files from composites/
# through: GraXpert background extraction -> SPCC colour calibration ->
# a single calibrated stretch curve, replacing the earlier StarNet +
# VeraLux HMS + StarComposer pipeline entirely.
#
# Why the architecture changed
# -----------------------------
# The previous version split each image into a starless layer (stretched
# with an arcsinh/IHS curve) and a star mask (StarNet-extracted, stretched
# and recombined separately). That split was the root cause of a long
# chain of problems: StarNet extraction noise contaminating black-point
# statistics, hard edges at star boundaries needing a blur fix, background
# colour speckle in empty starfields, and none of it ever quite matching
# the quality of doing the stretch directly.
#
# The current approach instead applies ONE curve directly to the whole
# composited image, per channel -- exactly matching a manual workflow of
# repeated Generalized Hyperbolic Stretch (GHS) passes in Siril, each
# with the symmetry point set at the current histogram peak, plus an
# occasional highlight-taming pass to keep the black point from drifting
# too light. That curve was calibrated directly from a real
# linear/stretched image pair (5 manual passes, SP at histogram peak,
# modest stretch factor ~1.35, occasional darken-from-0.95 pass to hold
# the peak near 0.12) and reproduces it with a mean pixel error of ~0.0006
# (visually indistinguishable) when reapplied. The curve is expressed in
# coordinates RELATIVE to each channel's own histogram peak, so a new
# image's own peak/background level re-anchors the same curve shape --
# this is what makes it generalise across panels with different exposure
# or background levels, the same way manually re-picking the peak as SP
# for a new image would.
#
# Steps (all 4 always logged; skipped steps say "skipped"):
#
#   [1/4]  GraXpert BGE          -- optional: RUN_BGE = True (default)
#          Background extraction on the linear composite before SPCC.
#
#   [2/4]  GraXpert Denoise      -- optional: RUN_DENOISE = False (default)
#          Denoising after BGE on gradient-free data.
#
#   [3/4]  SPCC colour calibration -- optional: RUN_SPCC = True (default)
#          Auto-detects wideband (LRGB) vs narrowband (SHO/HSO).
#          Set False for SHO after running VeraLux Alchemy manually.
#
#   [4/4]  Universal calibrated stretch, per channel, then save 32-bit
#          FITS -> result_fits/GLAT*_stretched_result.fits
#
# Prerequisites
# -------------
#   - Run Galactic_2_Composite.py first -> composites/GLAT*_(LRGB|SHO|HSO).fits
#   - Plate-solve each composite with ASTAP
#   - Crop registration border artifacts consistently across all panels
#   - Siril 1.4.0 or later
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

# Optional processing steps -- set False to skip
RUN_BGE     = True    # GraXpert background extraction before SPCC
RUN_DENOISE = False   # GraXpert denoise after BGE

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

# SPCC sensor and filter names -- these MUST match EXACTLY (including
# case and spacing) the names shown in Siril's SPCC dialog combo boxes,
# since Siril requires an exact string match. To find the exact names
# for your gear, run these commands in Siril's own command line (not in
# this script) and read the printed list:
#   spcc_list monosensor      (or oscsensor for one-shot-colour cameras)
#   spcc_list redfilter
#   spcc_list greenfilter
#   spcc_list bluefilter
# Then copy the exact strings below. If a name has spaces (most do), keep
# them here as plain strings -- this script's own quoting (_quote_if_needed)
# already wraps whole arguments containing spaces correctly for Siril.
#
# Once set here, SPCC is told the sensor/filters explicitly on every run,
# rather than depending on whatever was last selected in the GUI (which is
# what was silently wrong before -- Siril remembers the last-used GUI
# selection across sessions, so a wrong one-time selection quietly stays
# wrong for every subsequent script run until corrected).
SPCC_SENSOR_MODE = "mono"     # "mono" or "osc"

# -- mono sensor + per-channel filters (used when SPCC_SENSOR_MODE="mono") --
SPCC_MONO_SENSOR = "IMX585"        # exact name from `spcc_list monosensor`
SPCC_RFILTER     = "Optolong R"    # exact name from `spcc_list redfilter`
SPCC_GFILTER     = "Optolong G"    # exact name from `spcc_list greenfilter`
SPCC_BFILTER     = "Optolong B"    # exact name from `spcc_list bluefilter`

# -- OSC sensor (used when SPCC_SENSOR_MODE="osc") --
SPCC_OSC_SENSOR = ""     # exact name from `spcc_list oscsensor`
SPCC_OSC_FILTER = ""     # exact name from `spcc_list oscfilter` (optional)
SPCC_OSC_LPF    = ""     # exact name from `spcc_list osclpf` (optional)

# Optional: white reference (default "Average Spiral Galaxy" if left blank).
# Exact name from `spcc_list whiteref`.
SPCC_WHITEREF = ""

# Optional background tolerance for SPCC's own automatic background
# sampling (used internally for its background-neutralization step --
# SPCC always tries to realign the background to neutral gray as part of
# its calibration, using whatever pixels it decides count as "background").
# If different panels show different colour casts (e.g. "too purple" vs
# "too green" vs "too dark" on the same mosaic), a likely cause is this
# automatic sample picking up different amounts of faint nebulosity/gradient
# in some panels but not others, skewing their calibration slightly
# differently. Tightening this (smaller values = more conservative, only
# very dim/uniform pixels count as background) can make SPCC's background
# selection -- and therefore the calibration -- more consistent panel to
# panel. Format is "lower,upper" as Siril expects; leave blank to use
# Siril's own default.
SPCC_BGTOL = ""    # e.g. "0.01,0.1" -- tune to taste, blank = Siril default

# GHS_PEAK_HIST_BINS controls the resolution of the histogram used to find
# each channel's background peak (the reference point the calibrated
# curve is anchored to, matching "pick the peak as the symmetry point").
# Higher = more precise peak location but slightly slower; 3000 is a good
# default for typical panel sizes.
GHS_PEAK_HIST_BINS = 3000

# Neutral-lock correction for the "shoulder" brightness zone
# --------------------------------------------------------------
# Discovered by direct comparison against a real linear/stretched pair:
# a pixel with only ~9% relative difference between its raw R/G/B values
# (essentially neutral, e.g. raw [0.0127, 0.0117, 0.0116]) can come out
# of the stretch as [0.77, 0.72, 0.73] -- a much larger, visibly-coloured
# gap. This isn't unique to this script's reconstruction; the SAME
# divergence was confirmed present in the real manually-stretched
# reference image too, to within 0.001. It happens because ANY strongly
# compressive curve amplifies small relative input differences wherever
# its slope is still steep -- true independent of whether channels are
# stretched independently or via a shared luminance ratio (both were
# tested; luminance-ratio was actually slightly worse for this case).
#
# The fix: detect pixels whose RAW channels are already close to each
# other (likely genuinely neutral, or a calibration-noise-level
# difference that shouldn't be dramatised) within a brightness "shoulder"
# window -- background itself doesn't need this (already forced neutral
# by the per-channel peak match) and clearly-coloured bright stars don't
# need it either (their raw spread is well above the threshold, so they
# pass through completely unaffected) -- and pull just that shoulder
# region toward a shared neutral (luminance) output. Verified: this
# reduces a 0.049 output spread down to 0.002 for the discovered example,
# while genuinely coloured stars (raw spread > NEUTRAL_LOCK_SPREAD_HIGH)
# were confirmed pixel-for-pixel UNCHANGED, and overall reconstruction
# fidelity against the real reference only softened from 0.0006 to 0.0007
# mean absolute error.
NEUTRAL_LOCK_XREL_RISE = (1.2, 3.0)     # brightness window (in x_rel) where
NEUTRAL_LOCK_XREL_FALL = (10.0, 40.0)   # the correction ramps on, then off
NEUTRAL_LOCK_SPREAD_LOW  = 0.15   # raw relative spread below this -> treat
                                  # as neutral, pull toward gray
NEUTRAL_LOCK_SPREAD_HIGH = 0.40   # raw relative spread above this -> treat
                                  # as genuinely coloured, leave untouched

# Composite suffixes -- matches Galactic_2_Composite SUFFIX_BY_MODE
COMPOSITE_SUFFIXES = ("_LRGB", "_HSO", "_SHO")

SUFFIX_CC_LINEAR = "_cc_linear"    # post-BGE/SPCC linear result, kept for diagnosis
SUFFIX_RESULT    = "_stretched_result"

FITS_EXTENSIONS = {".fits", ".fit", ".fts"}
# ---------------------------------------------------------------------------


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


def _build_spcc_args(narrowband):
    """
    Build the spcc command's argument list from the SPCC_* config, so the
    sensor and filters are specified explicitly on every run instead of
    depending on whatever was last selected in Siril's GUI (which is what
    silently stays wrong indefinitely once set incorrectly once, since
    Siril remembers the last GUI selection across sessions).

    When narrowband=True, per-channel filter arguments are omitted (Siril
    ignores them in that mode and synthesises NB filter curves instead),
    but the sensor itself is still passed since its QE curve still matters.
    """
    args = ["spcc"]

    if SPCC_SENSOR_MODE == "osc":
        if SPCC_OSC_SENSOR:
            args.append("-oscsensor=" + SPCC_OSC_SENSOR)
        if not narrowband:
            if SPCC_OSC_FILTER:
                args.append("-oscfilter=" + SPCC_OSC_FILTER)
            if SPCC_OSC_LPF:
                args.append("-osclpf=" + SPCC_OSC_LPF)
    else:
        if SPCC_MONO_SENSOR:
            args.append("-monosensor=" + SPCC_MONO_SENSOR)
        if not narrowband:
            if SPCC_RFILTER:
                args.append("-rfilter=" + SPCC_RFILTER)
            if SPCC_GFILTER:
                args.append("-gfilter=" + SPCC_GFILTER)
            if SPCC_BFILTER:
                args.append("-bfilter=" + SPCC_BFILTER)

    if narrowband:
        args.append("-narrowband")
    if SPCC_BGTOL:
        args.append("-bgtol=" + SPCC_BGTOL)
    if SPCC_WHITEREF:
        args.append("-whiteref=" + SPCC_WHITEREF)

    return args


# ---------------------------------------------------------------------------
# Calibrated universal stretch curve
#
# Derived from a real linear/stretched image pair: 5 manual GHS passes in
# Siril, symmetry point re-picked at the current histogram peak each time,
# modest stretch factor (~1.35), with an occasional highlight-taming pass
# (SP=0.95, darkening) to hold the peak near 0.12 when darks drifted too
# light. Fitted via isotonic regression against >1M sampled pixel pairs
# across all three channels (pooled, since per-channel curves in
# peak-relative coordinates were found to be nearly identical), then
# compressed to a 152-point monotonic lookup table.
#
# Reapplying this exact curve to the calibration image reproduces the
# real stretched result with a mean absolute pixel error of ~0.0006
# (visually indistinguishable) -- see chat history for the validation.
#
# The X axis is in units of "multiples of this channel's own histogram
# peak" (x_rel = raw_value / channel_peak), NOT absolute pixel value --
# this is what lets the same curve re-anchor itself to a different
# panel's own background level, the same way manually re-picking the
# peak as SP for a new image would.
# ---------------------------------------------------------------------------
GHS_LUT_X = [
    0.000000, 0.438443, 0.438882, 0.457427, 0.476756, 0.496902, 0.517899, 0.539783,
    0.562592, 0.586365, 0.611142, 0.636967, 0.663882, 0.691935, 0.721174, 0.751647,
    0.783409, 0.816513, 0.851015, 0.886976, 0.924456, 0.963519, 1.004234, 1.046668,
    1.090896, 1.136993, 1.185038, 1.235113, 1.287303, 1.341700, 1.398394, 1.457485,
    1.519072, 1.583262, 1.650164, 1.719893, 1.792569, 1.868316, 1.947263, 2.029546,
    2.115307, 2.204691, 2.297852, 2.394950, 2.496151, 2.601628, 2.711562, 2.826141,
    2.945562, 3.070030, 3.199757, 3.334965, 3.475887, 3.622764, 3.775847, 3.935399,
    4.101693, 4.275014, 4.455658, 4.643936, 4.840170, 5.044696, 5.257864, 5.480040,
    5.711604, 5.952953, 6.204500, 6.466677, 6.739932, 7.024734, 7.321570, 7.630950,
    7.953403, 8.289481, 8.639760, 9.004841, 9.385349, 9.781935, 10.195280, 10.626091,
    11.075106, 11.543094, 12.030858, 12.539233, 13.069090, 13.621336, 14.196918, 14.796821,
    15.422074, 16.073748, 16.752959, 17.460870, 18.198695, 18.967698, 19.769195, 20.604560,
    21.475224, 22.382679, 23.328480, 24.314246, 25.341666, 26.412501, 27.528585, 28.691831,
    29.904230, 31.167860, 32.484886, 33.857565, 35.288247, 36.779383, 38.333530, 39.953348,
    41.641612, 43.401216, 45.235174, 47.146627, 49.138851, 51.215257, 53.379404, 55.634999,
    57.985906, 60.436153, 62.989938, 65.651635, 68.425804, 71.317198, 74.330771, 77.471685,
    80.745321, 84.157287, 87.713430, 91.419840, 95.282868, 99.309132, 103.505529, 107.879249,
    112.437784, 117.188945, 122.140869, 127.302042, 132.681305, 138.287874, 144.131353, 150.221754,
    156.569510, 163.185496, 170.081047, 177.267976, 184.758594, 192.565736, 200.702775, 209.183653,
]

GHS_LUT_Y = [
    0.021085, 0.021085, 0.021085, 0.022625, 0.024230, 0.025903, 0.027647, 0.029464,
    0.031490, 0.033998, 0.036612, 0.039544, 0.042915, 0.046549, 0.050820, 0.055732,
    0.061356, 0.067945, 0.075713, 0.084852, 0.096098, 0.109762, 0.126173, 0.144791,
    0.164095, 0.184553, 0.205883, 0.228519, 0.251737, 0.276194, 0.301052, 0.326789,
    0.353455, 0.380427, 0.408145, 0.436215, 0.463415, 0.492013, 0.520048, 0.547807,
    0.575255, 0.601258, 0.628249, 0.652718, 0.677440, 0.700858, 0.723021, 0.744979,
    0.764922, 0.784545, 0.802317, 0.819118, 0.834518, 0.849977, 0.863847, 0.876504,
    0.887987, 0.899057, 0.908749, 0.917462, 0.926331, 0.933246, 0.940185, 0.945945,
    0.951323, 0.956033, 0.960405, 0.964235, 0.967801, 0.970968, 0.974017, 0.976649,
    0.978988, 0.981059, 0.982907, 0.984550, 0.986112, 0.987525, 0.988769, 0.989938,
    0.990967, 0.991849, 0.992730, 0.993452, 0.994125, 0.994727, 0.995303, 0.995794,
    0.996230, 0.996599, 0.996944, 0.997258, 0.997554, 0.997807, 0.998023, 0.998237,
    0.998422, 0.998585, 0.998732, 0.998866, 0.998978, 0.999094, 0.999188, 0.999273,
    0.999352, 0.999420, 0.999488, 0.999544, 0.999590, 0.999638, 0.999677, 0.999716,
    0.999746, 0.999778, 0.999803, 0.999827, 0.999848, 0.999867, 0.999884, 0.999899,
    0.999912, 0.999924, 0.999933, 0.999943, 0.999951, 0.999959, 0.999965, 0.999970,
    0.999975, 0.999979, 0.999983, 0.999986, 0.999988, 0.999991, 0.999992, 0.999994,
    0.999995, 0.999996, 0.999997, 0.999998, 0.999999, 0.999999, 0.999999, 1.000000,
    1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000,
]


def _channel_histogram_peak(arr, n_bins=3000):
    """
    Find the background level as the peak (mode) of a fine histogram --
    "pick the peak histogram point" from the manual workflow this curve
    was calibrated against. Ordinary composited LRGB data (unlike a
    StarNet star mask) isn't hard-floored at zero, so a plain histogram
    peak works directly here without needing the source-contamination
    handling the star-mask code required in the previous version.
    """
    import numpy as np
    a = arr.ravel()
    a = a[np.isfinite(a)]
    if a.size == 0:
        return 1e-6
    hi = float(np.percentile(a, 99.9))
    if hi <= 0:
        hi = max(float(a.max()), 1e-6)
    hist, edges = np.histogram(a, bins=n_bins, range=(0.0, hi))
    peak_idx = int(np.argmax(hist))
    return max(0.5 * (edges[peak_idx] + edges[peak_idx + 1]), 1e-9)


def _smoothstep(t):
    import numpy as np
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def universal_ghs_stretch(fits_path, out_path, n_bins=GHS_PEAK_HIST_BINS):
    """
    Apply the calibrated universal stretch curve to a linear FITS image,
    independently per channel, each anchored to that channel's own
    histogram peak. See the GHS_LUT_X/GHS_LUT_Y module comment for how
    this curve was derived and validated.

    A neutral-lock correction (see the module comment above
    NEUTRAL_LOCK_XREL_RISE) then pulls the "shoulder" brightness zone
    back toward neutral for pixels whose RAW channels were already close
    together, without affecting background (already neutral by
    construction) or genuinely coloured bright stars (well above the raw
    spread threshold, left untouched).

    Returns (ok, peaks) -- peaks is a list of the per-channel background
    levels found, useful for logging/diagnosing consistency across panels.
    """
    try:
        import numpy as np
        from astropy.io import fits as _afits

        with _afits.open(str(fits_path)) as hdul:
            header = hdul[0].header.copy()
            data = hdul[0].data.astype(np.float64)

        mono = data.ndim == 2
        if mono:
            data = data[np.newaxis]

        max_val = data.max()
        if max_val > 1.0:
            data = data / max_val

        n_ch = data.shape[0]
        peaks = []
        x_rel = np.empty_like(data)

        for c in range(n_ch):
            peak = _channel_histogram_peak(data[c], n_bins=n_bins)
            peaks.append(peak)
            x_rel[c] = data[c] / peak

        out_indep = np.empty_like(data)
        for c in range(n_ch):
            out_indep[c] = np.interp(x_rel[c], GHS_LUT_X, GHS_LUT_Y,
                                     left=GHS_LUT_Y[0], right=GHS_LUT_Y[-1])

        if n_ch >= 3:
            x_rel_avg = x_rel.mean(axis=0)
            L_out = np.interp(x_rel_avg, GHS_LUT_X, GHS_LUT_Y,
                              left=GHS_LUT_Y[0], right=GHS_LUT_Y[-1])

            raw_max = data.max(axis=0)
            raw_min = data.min(axis=0)
            raw_spread = (raw_max - raw_min) / np.maximum(raw_max, 1e-9)

            rise = _smoothstep(
                (x_rel_avg - NEUTRAL_LOCK_XREL_RISE[0])
                / (NEUTRAL_LOCK_XREL_RISE[1] - NEUTRAL_LOCK_XREL_RISE[0])
            )
            fall = 1.0 - _smoothstep(
                (x_rel_avg - NEUTRAL_LOCK_XREL_FALL[0])
                / (NEUTRAL_LOCK_XREL_FALL[1] - NEUTRAL_LOCK_XREL_FALL[0])
            )
            window = np.clip(rise * fall, 0.0, 1.0)

            color_confidence = _smoothstep(
                (raw_spread - NEUTRAL_LOCK_SPREAD_LOW)
                / (NEUTRAL_LOCK_SPREAD_HIGH - NEUTRAL_LOCK_SPREAD_LOW)
            )
            pull_to_gray = window * (1.0 - color_confidence)

            out = out_indep * (1.0 - pull_to_gray) + L_out * pull_to_gray
        else:
            out = out_indep

        out = np.clip(out, 0.0, 1.0)
        if mono:
            out = out[0]

        out_hdu = _afits.PrimaryHDU(out.astype(np.float32), header=header)
        out_hdu.writeto(str(out_path), overwrite=True)
        return True, peaks

    except Exception:
        return False, None


def scan_all_panels(home_dir):
    """
    Scan home_dir/composites/ for GLAT*_(LRGB|HSO|SHO)[_NNNs].fits files
    and report the status of EVERY one found -- "SKIP" if its result_fits/
    output already exists, "QUEUED" if it still needs to be processed.

    The optional trailing exposure postfix (e.g. "_1200s", written by
    Galactic_2_Composite.py) is matched via regex rather than a simple
    .endswith() check on the composite suffix, since the postfix sits
    AFTER "_LRGB"/"_HSO"/"_SHO" and would otherwise break detection
    entirely. The exposure postfix (if present) is carried forward into
    the result_fits output filename too, so it stays visible at every
    pipeline stage.

    Returns a list of dicts: {prefix, composite_suffix, exposure_suffix,
    path, result_path, status}, sorted by filename. This is the single
    source of truth for what will run -- printed in full before any
    processing starts, so it's never ambiguous why more (or fewer) panels
    ran than expected.
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
    """Run steps 1-4 for one plate-solved composite panel."""
    siril_log(siril, " ")
    siril_log(siril, "=" * 60)
    siril_log(siril, "Panel: " + prefix + "  [" + composite_suffix.strip("_") + "]"
              + (" " + exposure_suffix.strip("_") if exposure_suffix else ""))
    siril_log(siril, "Input: " + lrgb_path.name)
    siril_log(siril, "=" * 60)

    process_dir = home_dir / "process"
    process_dir.mkdir(exist_ok=True)

    result_fits_dir = home_dir / "result_fits"
    result_tiff_dir = home_dir / "result_tiff"
    result_fits_dir.mkdir(exist_ok=True)
    result_tiff_dir.mkdir(exist_ok=True)

    cs = composite_suffix
    es = exposure_suffix   # e.g. "_1200s", or "" if unknown -- carried
                           # forward from the composite filename so total
                           # exposure stays visible at every pipeline stage
    result_out = result_fits_dir / (prefix + cs + es + SUFFIX_RESULT + ".fits")
    cc_linear_path = process_dir / (prefix + cs + es + SUFFIX_CC_LINEAR + ".fits")

    cmd_safe(siril, "cd", str(home_dir))

    # ------------------------------------------------------------------
    # Steps 1-2: GraXpert BGE and Denoise (both optional via RUN_ flags)
    # ------------------------------------------------------------------
    if not cmd_safe(siril, "load", str(lrgb_path)):
        siril_log(siril, "  [ERROR] Cannot load " + lrgb_path.name)
        return False

    if RUN_BGE:
        siril_log(siril, "  [1/4] GraXpert background extraction (BGE)...")
        bge_ok = cmd_safe(siril, "pyscript", "GraXpert-AI.py", "-bge")
        if not bge_ok:
            siril_log(siril, "  [WARNING] GraXpert BGE failed -- continuing.")
    else:
        siril_log(siril, "  [1/4] BGE skipped (RUN_BGE = False).")

    if RUN_DENOISE:
        siril_log(siril, "  [2/4] GraXpert denoise...")
        denoise_ok = cmd_safe(siril, "pyscript", "GraXpert-AI.py", "-denoise", "-strength=0.5")
        if not denoise_ok:
            siril_log(siril, "  [WARNING] GraXpert denoise failed -- continuing.")
    else:
        siril_log(siril, "  [2/4] Denoise skipped (RUN_DENOISE = False).")

    # ------------------------------------------------------------------
    # Step 3: Colour Calibration -- SPCC preferred, PCC with Gaia DR3 fallback
    # ------------------------------------------------------------------
    if not RUN_SPCC:
        siril_log(siril, "  [3/4] Colour calibration SKIPPED (RUN_SPCC = False).")
        siril_log(siril, "  Assuming SPCC/Alchemy was already applied manually.")
    else:
        siril_log(siril, "  [3/4] Colour calibration (SPCC -> PCC fallback)...")

        is_narrowband = (
            (home_dir / "Ha" / "stacked").is_dir() or
            (home_dir / "Sii" / "stacked").is_dir() or
            (home_dir / "Oiii" / "stacked").is_dir()
        ) and not (home_dir / "L" / "stacked").is_dir()

        if is_narrowband:
            siril_log(siril, "  Narrowband mode detected -- using SPCC -narrowband"
                      + " (sensor QE still applied, per-channel filters ignored)")
            cc_ok = cmd_safe(siril, *_build_spcc_args(narrowband=True))
        else:
            siril_log(siril, "  Wideband mode -- SPCC with " + SPCC_SENSOR_MODE
                      + " sensor "
                      + (SPCC_MONO_SENSOR if SPCC_SENSOR_MODE != "osc" else SPCC_OSC_SENSOR))
            cc_ok = cmd_safe(siril, *_build_spcc_args(narrowband=False))

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

    if not cmd_safe(siril, "save", str(cc_linear_path)):
        siril_log(siril, "  [ERROR] Cannot save cc_linear.")
        return False

    # ------------------------------------------------------------------
    # Step 4: Universal calibrated stretch (see module comment above
    # GHS_LUT_X for how this curve was derived), then save.
    # ------------------------------------------------------------------
    siril_log(siril, "  [4/4] Applying calibrated stretch curve...")
    ok, peaks = universal_ghs_stretch(cc_linear_path, result_out)
    if not ok:
        siril_log(siril, "  [ERROR] Stretch failed.")
        return False

    peaks_str = ", ".join("{:.5f}".format(p) for p in peaks) if peaks else "?"
    siril_log(siril, "  Per-channel background peaks: " + peaks_str)
    siril_log(siril, "  Saved: " + result_out.name)
    siril_log(siril, "  Next: run Galactic_4_Tiff.py to export TIFFs for stitching.")

    cmd_safe(siril, "cd", str(home_dir))
    siril_log(siril, "  Panel " + prefix + " complete.")
    return True


def main():
    siril = s.SirilInterface()
    try:
        siril.connect()
        siril_log(siril, "Galactic_3_Stretch v2.0.0 connected.")
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