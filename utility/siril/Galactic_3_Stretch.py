# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_3_Stretch.py
# Version: 1.2.1
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
HMS_LOG_D     = 8.8    # VeraLux HyperMetric Stretch Log D
SC_STAR_LOG_D = 10.5   # VeraLux StarComposer "Star Intensity Log D" -- only
                        # used as the suggested value printed when running
                        # the real VeraLux GUI. NOT used by the headless
                        # bypass below (see SC_STAR_MIDTONE) -- VeraLux's
                        # internal units for this parameter don't map onto
                        # the arcsinh IHS formula used elsewhere in this
                        # script; reusing it caused runaway clipping
                        # (flat-white, blocky stars with no colour).

# BYPASS_VERALUX_STARCOMPOSER = True skips the VeraLux StarComposer GUI
# (which needs the starless + starmask manually selected for every single
# panel) and recombines them headlessly instead:
#   1. The starmask (raw, from StarNet) is stretched independently using a
#      midtone transfer function (SC_STAR_MIDTONE) -- the same style of
#      curve Siril/PixInsight use for stretching, which spreads the full
#      brightness range smoothly instead of crushing everything near the
#      top the way a very large arcsinh D does.
#   2. Colour is restored via a per-pixel ratio, then instead of clipping
#      each channel independently at 1.0 (which desaturates a pixel to
#      white the instant one channel overflows), the whole RGB triple is
#      rescaled down so its brightest channel lands at 1.0 -- preserving
#      true star colour even at the brightest cores.
#   3. Pixels within SC_NOISE_FLOOR_K sigma of the starmask's own
#      background are suppressed toward BLACK (not gray -- unlike the
#      main background stretch, the star layer's "background" should
#      stay at zero so it doesn't brighten the final composite). This
#      stops StarNet's extraction noise from adding speckle when blended.
#   4. The stretched star layer is composited onto the stretched starless
#      image using SC_BLEND_MODE ("screen" by default -- the standard
#      astro blend for recombining stars, since it never double-brightens
#      the background and doesn't harshly clip star cores).
BYPASS_VERALUX_STARCOMPOSER = True   # True = headless recombine, False = VeraLux GUI
SC_STAR_MIDTONE  = 0.01       # Midtone stretch for the star layer (0-1).
                              # Lower = more aggressive (pulls faint stars
                              # up harder); higher = gentler. Unrelated to
                              # SC_STAR_LOG_D's units -- start around 0.15-
                              # 0.35 and adjust to taste.
SC_PROTECT_B     = 4.0        # Unused by the headless bypass (kept for the
                              # VeraLux GUI prompt only).
SC_BLEND_MODE    = "screen"   # "screen" | "lighten" | "add"
SC_NOISE_FLOOR_K = 2.0        # Sigma above starmask background where star
                              # colour/brightness starts being restored
                              # (fully restored by 3x this). Suppresses
                              # StarNet extraction noise in the star layer.

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
# opens its dialog inside a scripted pipeline. The math is the same IHS
# stretch VeraLux HMS uses (vector colour preservation), but with three
# additions aimed at making panels stretch CONSISTENTLY with each other:
#
#   1. Per-panel auto-solved Log D (HMS_AUTO_SOLVE_LOGD).
#      A single fixed Log D stretches panels differently depending on how
#      bright their background already was -- a starfield-only panel (near
#      -zero background) needs a much bigger apparent stretch than a
#      dust-rich MW-core panel to reach the same visual brightness, which
#      is exactly what makes empty panels look "over-stretched" and turns
#      faint background noise into visible colour speckle. Instead, this
#      solves for the Log D that brings THIS panel's own background to the
#      same HMS_TARGET_BG for every panel, so all panels end up at a
#      matching background brightness regardless of how much real signal
#      they contain.
#
#   2. Background neutralization (HMS_NEUTRALIZE_BACKGROUND).
#      Even after SPCC, the R/G/B background pedestals can differ by a
#      hair between panels -- invisible in linear data, but exactly what
#      the colour-preserving ratio stretch amplifies into visible colour
#      casts in starfields. This measures each channel's sigma-clipped
#      background median and shifts channels additively (never
#      multiplicatively, which would also shift star colours) so the
#      background is truly neutral before stretching.
#
#   3. SNR-based colour desaturation (HMS_NOISE_FLOOR_K).
#      A single shared luminance ratio applied to R/G/B can't create
#      colour noise by itself -- it scales all three channels by the same
#      number, preserving their existing relative proportions. So instead
#      of trying to tame the ratio, pixels are explicitly desaturated
#      toward neutral gray the closer they are to the background: below
#      HMS_NOISE_FLOOR_K sigma above the background they are forced fully
#      gray (at their own stretched luminance), and above 3x that they
#      keep full colour, with a smooth transition between. Real signal
#      (nebulosity, dust, stars) sits well above the noise and keeps its
#      natural colour; only noise-dominated background is flattened.
#
# These three apply only when BYPASS_VERALUX_HMS = True. If you run the
# real VeraLux GUI instead, the script still computes and prints a
# suggested Log D for that panel (using #1's maths) so you can type in a
# consistent value by hand across panels -- but #2 and #3 only happen in
# the headless path.
BYPASS_VERALUX_HMS = True   # True = headless stretch, False = VeraLux GUI

HMS_TARGET_BG  = 0.52        # Target post-stretch background level (0-1).
                              # The SAME value is targeted for every panel,
                              # which is what makes their backgrounds match.
HMS_PROTECT_B  = 6.0         # Highlight protection (VeraLux "Protect b")
HMS_COLOR_GRIP = 0.0         # 0.0=scientific vector preserve, 1.0=scalar stretch

HMS_AUTO_SOLVE_LOGD = True   # Solve Log D per panel to hit HMS_TARGET_BG.
                              # If False, falls back to the fixed HMS_LOG_D
                              # below for every panel (the old behaviour).
HMS_NEUTRALIZE_BACKGROUND = True   # Additively equalize R/G/B background
                                     # pedestals before stretching.
HMS_NOISE_FLOOR_K = 2.0      # Sigma above background where colour starts
                              # being restored (full colour by 3x this).
                              # Higher = more background forced to neutral
                              # gray. 0 effectively disables desaturation.

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
    args = tuple(_quote_if_needed(a) for a in args)
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

def _sigma_clipped_median_std(arr, sigma=3.0, iters=5):
    """
    Simple iterative sigma-clipped median/std, dependency-free (no
    astropy.stats needed). Used to get a background estimate that ignores
    stars (which sit far above the background and get clipped out after
    a couple of iterations).
    """
    import numpy as np
    a = arr.astype(np.float64).ravel()
    a = a[np.isfinite(a)]
    if a.size == 0:
        return 0.0, 0.0
    for _ in range(iters):
        med = np.median(a)
        std = np.std(a)
        if std <= 0:
            break
        keep = np.abs(a - med) < sigma * std
        kept = a[keep]
        if kept.size == a.size or kept.size < 10:
            break
        a = kept
    return float(np.median(a)), float(np.std(a))


def _solve_log_d_for_target(bg, target_bg, b,
                            log_d_min=-1.0, log_d_max=12.0,
                            tol=1e-4, max_iter=60):
    """
    Solve for the Log D that maps a given background level 'bg' to
    'target_bg' under the IHS stretch (with shadow-protection value b),
    via bisection. ihs(bg) is monotonically increasing in D (more stretch
    -> brighter background), so a unique root normally exists in-range.

    This is what makes panels come out with a MATCHING background
    brightness regardless of how much real signal (nebulosity/dust) each
    one started with -- each panel gets exactly the Log D it individually
    needs to reach the same target, rather than one fixed Log D that
    over- or under-stretches depending on the panel's content.

    Returns the solved Log D (the exponent, i.e. D = 10**log_d).
    """
    import math
    if bg is None or not math.isfinite(bg):
        return 3.8   # sane fallback if background estimation failed
    bg = max(bg, 1e-8)
    if target_bg <= bg:
        # Background is already at or above target -- minimal stretch.
        return log_d_min

    arcsinh_b = math.asinh(b)

    def ihs_bg(log_d):
        D = 10.0 ** log_d
        norm = math.asinh(D + b) - arcsinh_b
        if abs(norm) < 1e-15:
            norm = 1e-15
        return (math.asinh(D * bg + b) - arcsinh_b) / norm

    lo, hi = log_d_min, log_d_max
    f_lo = ihs_bg(lo) - target_bg
    f_hi = ihs_bg(hi) - target_bg
    if f_lo >= 0:
        return lo
    if f_hi <= 0:
        return hi   # even max stretch can't reach target -- extreme case

    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        f_mid = ihs_bg(mid) - target_bg
        if abs(f_mid) < tol:
            return mid
        if f_mid > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def estimate_panel_log_d(fits_path, target_bg, protect_b,
                         neutralize_bg=True):
    """
    Read a FITS file and compute the Log D that would bring ITS background
    to target_bg. Used both by the headless bypass (to actually apply it)
    and, when running the real VeraLux GUI, purely as a printed suggestion
    so the same target can be typed in by hand across panels for
    consistency.

    Returns (log_d, bg_level) or (None, None) on failure.
    """
    try:
        import numpy as np
        from astropy.io import fits as _afits

        with _afits.open(str(fits_path)) as hdul:
            data = hdul[0].data.astype(np.float64)

        mono = data.ndim == 2
        if mono:
            data = data[np.newaxis]

        max_val = data.max()
        if max_val > 1.0:
            data = data / max_val

        n_ch = data.shape[0]
        bg_meds = []
        for c in range(n_ch):
            med, _std = _sigma_clipped_median_std(data[c])
            bg_meds.append(med)
        bg_meds = np.array(bg_meds)

        if neutralize_bg and n_ch >= 3:
            bg_level = float(bg_meds.min())
        else:
            bg_level = float(np.mean(bg_meds))

        b = 10.0 ** (-protect_b)
        log_d = _solve_log_d_for_target(bg_level, target_bg, b)
        return log_d, bg_level

    except Exception:
        return None, None


def hms_stretch(fits_path, out_path, protect_b, color_grip,
                target_bg=0.20, auto_solve=True, fixed_log_d=3.8,
                neutralize_bg=True, noise_floor_k=3.0):
    """
    Headless equivalent of VeraLux HyperMetric Stretch, extended for
    cross-panel consistency:

      1. Load image from fits_path (32-bit float, values in [0,1]).
      2. Normalise to [0,1] if values exceed 1.0 (StarNet rescaling artefact).
      3. Background neutralization (if neutralize_bg): measure each
         channel's sigma-clipped background median and additively equalize
         them, so the background is truly neutral before stretching. This
         removes the tiny per-panel colour casts that otherwise get
         amplified into visible speckle in low-signal starfields.
      4. Extract luminance: L = mean(R, G, B).
      5. Solve Log D (if auto_solve) so THIS panel's background reaches
         target_bg -- the same target for every panel -- instead of using
         one fixed Log D that stretches different panels by different
         effective amounts.
      6. Apply IHS to L:
            b    = 10 ** (-protect_b)
            D    = 10 ** log_d
            norm = arcsinh(D+b) - arcsinh(b)
            L_s  = (arcsinh(D*L + b) - arcsinh(b)) / norm
      7. Project stretched luminance back to RGB, then blend each pixel
         toward neutral gray (at that pixel's own stretched luminance)
         based on its SNR above the background: a single shared ratio
         cannot by itself create colour noise (it scales R/G/B by the
         same number, preserving their relative proportions), so the
         actual fix for colour speckle in noise-dominated regions is to
         explicitly kill their colour and let true signal (nebulosity,
         dust, stars) keep full saturation once it's clearly above the
         noise:
            snr    = L / background_sigma
            weight = smoothstep(snr, noise_floor_k, noise_floor_k * 3)
                     0 at/below the noise floor (forced neutral gray),
                     1 well above it (full colour preserved)
            colour_channel = data[c] * (L_s / L)
            out[c] = weight*colour_channel + (1-weight)*L_s
         color_grip then blends toward the fully-independent per-channel
         IHS stretch on top of that, same as before.
      8. Clip to [0,1], save to out_path.

    Returns (ok, log_d_used, bg_before, bg_after) -- the last three are
    None if ok is False, useful for logging cross-panel consistency.
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

        # ------------------------------------------------------------
        # Background neutralization (additive, per-channel).
        # Bring every channel's background pedestal down to the level
        # of the darkest channel, so R=G=B in the background before any
        # stretch or ratio maths touches it.
        # ------------------------------------------------------------
        bg_meds = []
        for c in range(n_ch):
            med, _std = _sigma_clipped_median_std(data[c])
            bg_meds.append(med)
        bg_meds = np.array(bg_meds)

        if neutralize_bg and n_ch >= 3:
            bg_min = float(bg_meds.min())
            for c in range(n_ch):
                shift = bg_meds[c] - bg_min
                if shift > 0:
                    data[c] = np.clip(data[c] - shift, 0.0, None)
            bg_before = bg_min
        else:
            bg_before = float(np.mean(bg_meds))

        # Luminance (post-neutralization)
        if n_ch >= 3:
            L = (data[0] + data[1] + data[2]) / 3.0
        else:
            L = data[0].copy()

        l_bg_med, l_bg_std = _sigma_clipped_median_std(L)

        # ------------------------------------------------------------
        # Solve or use fixed Log D
        # ------------------------------------------------------------
        b = 10.0 ** (-protect_b)   # small positive value ~1e-6 for protect_b=6
        if auto_solve:
            log_d = _solve_log_d_for_target(l_bg_med, target_bg, b)
        else:
            log_d = fixed_log_d

        D = 10.0 ** log_d
        arcsinh_b    = np.arcsinh(b)
        arcsinh_norm = np.arcsinh(D + b) - arcsinh_b
        if abs(arcsinh_norm) < 1e-12:
            arcsinh_norm = 1e-12

        def ihs(x):
            return (np.arcsinh(D * np.clip(x, 0, None) + b) - arcsinh_b) / arcsinh_norm

        L_s = ihs(L)
        bg_after = float(ihs(l_bg_med))

        # ------------------------------------------------------------
        # Colour projection with SNR-based desaturation.
        #
        # A shared per-pixel ratio (L_s / L) applied equally to R, G, B
        # cannot itself introduce colour variance -- it preserves whatever
        # relative proportions were already in the linear data. So instead
        # of trying to tame the ratio's denominator, we directly suppress
        # colour in pixels that are noise-dominated: below noise_floor_k
        # sigma above background they are forced to neutral gray (at their
        # own stretched luminance), and above noise_floor_k*3 sigma they
        # keep full colour, with a smooth transition between the two.
        # ------------------------------------------------------------
        eps = 1e-12
        l_bg_std_safe = max(l_bg_std, 1e-9)
        snr = (L - l_bg_med) / l_bg_std_safe

        lo_snr = noise_floor_k
        hi_snr = noise_floor_k * 3.0
        if hi_snr <= lo_snr:
            hi_snr = lo_snr + 1.0
        t = np.clip((snr - lo_snr) / (hi_snr - lo_snr), 0.0, 1.0)
        chroma_weight = t * t * (3.0 - 2.0 * t)   # smoothstep

        if n_ch >= 3:
            ratio = L_s / np.where(L > eps, L, eps)
            img_color = np.stack([
                data[c] * ratio for c in range(n_ch)
            ])
            img_gray = np.broadcast_to(L_s, img_color.shape)
            img_sci = np.clip(
                chroma_weight * img_color + (1.0 - chroma_weight) * img_gray,
                0.0, 1.0,
            )

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
        return True, log_d, bg_before, bg_after

    except Exception as exc:
        return False, None, None, None
    

def _mtf(x, m):
    """
    Midtone Transfer Function (the same curve Siril/PixInsight use for
    histogram stretching): maps 0->0, m->0.5, 1->1, smoothly and without
    the runaway compression an arcsinh curve produces at very high D --
    which is what was crushing almost the entire star brightness range
    into a narrow band near 1.0 and clipping colour to flat white.
    """
    import numpy as np
    m = min(max(m, 1e-6), 1.0 - 1e-6)
    x = np.clip(x, 0.0, None)
    denom = (2.0 * m - 1.0) * x - m
    return np.clip(((m - 1.0) * x) / denom, 0.0, 1.0)


def star_composite(starless_path, starmask_path, out_path,
                   star_midtone, protect_b, blend_mode="screen",
                   noise_floor_k=3.0):
    """
    Headless equivalent of VeraLux StarComposer: recombine a stretched
    starless image with its (raw, linear) starmask, without needing the
    GUI dialog opened and its files selected by hand for every panel.

    Algorithm:
      1. Load the starless image (already stretched) and the raw starmask
         (from StarNet -- mostly black, with stars as bright features).
      2. Stretch the starmask independently using a midtone transfer
         function (star_midtone, in (0,1) -- NOT the same units as
         VeraLux's own "Star Intensity Log D"). MTF spreads the full
         brightness range smoothly instead of crushing everything near
         the top the way a very large arcsinh D does, which is what was
         causing flat-white, blocky stars with no colour.
      3. Project back to colour using a per-pixel ratio (vector colour
         preservation), then -- instead of hard-clipping each channel to
         1.0 independently, which desaturates a pixel toward white the
         moment any one channel overflows -- RESCALE the whole RGB
         triple down proportionally so its brightest channel lands at
         1.0. This keeps the true hue/saturation of every star, including
         the brightest cores, instead of bleaching them white.
      4. Low-SNR pixels (StarNet extraction noise, not real stars) are
         suppressed toward BLACK rather than gray -- the star layer's
         background should stay at zero so it doesn't brighten the final
         blend.
      5. Composite onto the starless image with blend_mode:
           "screen"  : 1 - (1-starless)*(1-star)   -- never over-brightens
                       the background, soft on bright overlaps (default,
                       matches the usual astro convention for stars)
           "lighten" : max(starless, star)          -- simpler, harder edge
           "add"     : clip(starless + star, 0, 1)  -- most aggressive

    Returns True on success, False on error.
    """
    try:
        import numpy as np
        from astropy.io import fits as _afits

        with _afits.open(str(starless_path)) as hdul:
            header = hdul[0].header.copy()
            base = hdul[0].data.astype(np.float64)
        with _afits.open(str(starmask_path)) as hdul:
            star_raw = hdul[0].data.astype(np.float64)

        mono_base = base.ndim == 2
        if mono_base:
            base = base[np.newaxis]
        mono_star = star_raw.ndim == 2
        if mono_star:
            star_raw = star_raw[np.newaxis]

        if base.max() > 1.0:
            base = base / base.max()
        if star_raw.max() > 1.0:
            star_raw = star_raw / star_raw.max()

        n_ch = star_raw.shape[0]

        if n_ch >= 3:
            L_star = (star_raw[0] + star_raw[1] + star_raw[2]) / 3.0
        else:
            L_star = star_raw[0].copy()

        star_bg_med, star_bg_std = _sigma_clipped_median_std(L_star)
        L_star_s = _mtf(L_star, star_midtone)

        # Suppress noise-dominated pixels toward BLACK (not gray -- see
        # docstring). Same smoothstep shape as the main stretch's chroma
        # blend, just targeting zero instead of a gray floor.
        eps = 1e-12
        star_bg_std_safe = max(star_bg_std, 1e-9)
        snr = (L_star - star_bg_med) / star_bg_std_safe
        lo_snr = noise_floor_k
        hi_snr = noise_floor_k * 3.0
        if hi_snr <= lo_snr:
            hi_snr = lo_snr + 1.0
        t = np.clip((snr - lo_snr) / (hi_snr - lo_snr), 0.0, 1.0)
        weight = t * t * (3.0 - 2.0 * t)

        if n_ch >= 3:
            ratio = L_star_s / np.where(L_star > eps, L_star, eps)
            star_color = np.stack([star_raw[c] * ratio for c in range(n_ch)])

            # Hue-preserving highlight rescale: if any channel overflows
            # 1.0, scale the WHOLE pixel's RGB down so the brightest
            # channel lands exactly at 1.0, instead of clipping each
            # channel independently (which destroys hue/saturation --
            # this is what turned coloured stars into flat white blobs).
            max_ch = np.max(star_color, axis=0)
            overflow_scale = np.where(max_ch > 1.0, 1.0 / np.maximum(max_ch, eps), 1.0)
            star_color = star_color * overflow_scale

            star_layer = np.clip(weight * star_color, 0.0, 1.0)
        else:
            star_layer = np.clip(weight * L_star_s[np.newaxis], 0.0, 1.0)

        # Match channel counts if one input is mono and the other RGB
        n_out = max(base.shape[0], star_layer.shape[0])
        if base.shape[0] == 1 and n_out > 1:
            base = np.repeat(base, n_out, axis=0)
        if star_layer.shape[0] == 1 and n_out > 1:
            star_layer = np.repeat(star_layer, n_out, axis=0)
        base = np.clip(base, 0.0, 1.0)

        if blend_mode == "lighten":
            out = np.maximum(base, star_layer)
        elif blend_mode == "add":
            out = base + star_layer
        else:   # "screen" (default)
            out = 1.0 - (1.0 - base) * (1.0 - star_layer)

        out = np.clip(out, 0.0, 1.0)

        if mono_base and mono_star:
            out = out[0]

        out_hdu = _afits.PrimaryHDU(out.astype(np.float32), header=header)
        out_hdu.writeto(str(out_path), overwrite=True)
        return True

    except Exception:
        return False

def scan_all_panels(home_dir):
    """
    Scan home_dir/composites/ for GLAT*_(LRGB|HSO|SHO).fits files and
    report the status of EVERY one found -- "SKIP" if its result_fits/
    output already exists, "QUEUED" if it still needs to be processed.

    Returns a list of dicts: {prefix, composite_suffix, path, result_path,
    status}, sorted by filename. This is the single source of truth for
    what will run -- printed in full before any processing starts, so
    it's never ambiguous why more (or fewer) panels ran than expected.
    """
    composites_dir = home_dir / "composites"
    if not composites_dir.is_dir():
        return []
    entries = []
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
        result_path = home_dir / "result_fits" / (prefix + composite_suffix + SUFFIX_RESULT + ".fits")
        status = "SKIP" if result_path.exists() else "QUEUED"
        entries.append({
            "prefix": prefix,
            "composite_suffix": composite_suffix,
            "path": p,
            "result_path": result_path,
            "status": status,
        })
    return entries


def find_lrgb_panels(home_dir):
    """
    Scan home_dir/process/ for plate-solved GLAT*_(LRGB|HSO|SHO).fits files.
    Returns list of (prefix, composite_suffix, lrgb_path) tuples, sorted by name.
    Skips panels where _stretched_result already exists in home_dir.
    """
    entries = scan_all_panels(home_dir)
    return [(e["prefix"], e["composite_suffix"], e["path"])
            for e in entries if e["status"] == "QUEUED"]


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
        siril_log(siril, "  [5/6] HyperMetric Stretch (target bg "
                  + str(HMS_TARGET_BG) + ")...")

        if BYPASS_VERALUX_HMS:
            siril_log(siril, "  Headless HMS (BYPASS_VERALUX_HMS = True)...")
            hms_ok, used_log_d, bg_before, bg_after = hms_stretch(
                stretch_source, stretched_starless,
                HMS_PROTECT_B, HMS_COLOR_GRIP,
                target_bg=HMS_TARGET_BG,
                auto_solve=HMS_AUTO_SOLVE_LOGD,
                fixed_log_d=HMS_LOG_D,
                neutralize_bg=HMS_NEUTRALIZE_BACKGROUND,
                noise_floor_k=HMS_NOISE_FLOOR_K,
            )
            if hms_ok:
                siril_log(siril, "  Headless HMS complete: " + stretched_starless.name)
                siril_log(siril, "  Log D used: {:.3f}   bg before/after: {:.5f} / {:.5f}"
                          .format(used_log_d, bg_before, bg_after))
                if not cmd_safe(siril, "load", str(stretched_starless)):
                    siril_log(siril, "  [ERROR] Cannot load headless stretch result.")
                    return False
            else:
                siril_log(siril, "  [ERROR] Headless HMS failed.")
                return False
        else:
            suggested_log_d, suggested_bg = estimate_panel_log_d(
                stretch_source, HMS_TARGET_BG, HMS_PROTECT_B,
                neutralize_bg=HMS_NEUTRALIZE_BACKGROUND)
            if suggested_log_d is not None:
                siril_log(siril, "  NOTE: Dialog will open -- for a background"
                          + " matching other panels, set Log D to {:.2f}"
                          .format(suggested_log_d)
                          + " (measured bg={:.5f}) and click Process."
                          .format(suggested_bg))
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
            if BYPASS_VERALUX_STARCOMPOSER:
                siril_log(siril, "  Headless StarComposer (BYPASS_VERALUX_STARCOMPOSER = True)...")
                siril_log(siril, "  Star midtone: " + str(SC_STAR_MIDTONE)
                          + "   blend=" + SC_BLEND_MODE)
                combined_out = process_dir / (prefix + cs + "_combined.fits")
                sc_ok = star_composite(
                    stretched_starless, starmask_out, combined_out,
                    star_midtone=SC_STAR_MIDTONE, protect_b=SC_PROTECT_B,
                    blend_mode=SC_BLEND_MODE, noise_floor_k=SC_NOISE_FLOOR_K,
                )
                if sc_ok:
                    siril_log(siril, "  Headless StarComposer complete: " + combined_out.name)
                    if not cmd_safe(siril, "load", str(combined_out)):
                        siril_log(siril, "  [ERROR] Cannot load headless composite result.")
                        siril_log(siril, "  [WARNING] Falling back to starless only.")
                        cmd_safe(siril, "load", str(stretched_starless))
                else:
                    siril_log(siril, "  [WARNING] Headless StarComposer failed -- using starless only.")
                    cmd_safe(siril, "load", str(stretched_starless))
            else:
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
        siril_log(siril, "  [5/6] HyperMetric Stretch on full image (target bg "
                  + str(HMS_TARGET_BG) + ")...")

        if BYPASS_VERALUX_HMS:
            siril_log(siril, "  Headless HMS (BYPASS_VERALUX_HMS = True)...")
            hms_ok2, used_log_d, bg_before, bg_after = hms_stretch(
                cc_linear_path, stretched_starless,
                HMS_PROTECT_B, HMS_COLOR_GRIP,
                target_bg=HMS_TARGET_BG,
                auto_solve=HMS_AUTO_SOLVE_LOGD,
                fixed_log_d=HMS_LOG_D,
                neutralize_bg=HMS_NEUTRALIZE_BACKGROUND,
                noise_floor_k=HMS_NOISE_FLOOR_K,
            )
            if hms_ok2:
                siril_log(siril, "  Headless HMS complete: " + stretched_starless.name)
                siril_log(siril, "  Log D used: {:.3f}   bg before/after: {:.5f} / {:.5f}"
                          .format(used_log_d, bg_before, bg_after))
                if not cmd_safe(siril, "load", str(stretched_starless)):
                    siril_log(siril, "  [ERROR] Cannot load headless stretch result.")
                    return False
            else:
                siril_log(siril, "  [ERROR] Headless HMS failed.")
                return False
        else:
            suggested_log_d, suggested_bg = estimate_panel_log_d(
                cc_linear_path, HMS_TARGET_BG, HMS_PROTECT_B,
                neutralize_bg=HMS_NEUTRALIZE_BACKGROUND)
            if suggested_log_d is not None:
                siril_log(siril, "  NOTE: Dialog will open -- for a background"
                          + " matching other panels, set Log D to {:.2f}"
                          .format(suggested_log_d)
                          + " (measured bg={:.5f}) and click Process."
                          .format(suggested_bg))
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

        all_entries = scan_all_panels(home_dir)

        if not all_entries:
            siril_log(siril, "No plate-solved LRGB panels found.")
            siril_log(siril, "Expected: GLAT*_LRGB.fits files in " + str(home_dir / "process"))
            siril_log(siril, "Plate-solve your LRGB files with ASTAP first.")
            siril.disconnect()
            return

        # Report the status of EVERY panel found -- makes it unambiguous
        # which ones will actually run and which are being skipped because
        # their result_fits/*_stretched_result.fits already exists.
        siril_log(siril, "Found " + str(len(all_entries)) + " composite panel(s):")
        for e in all_entries:
            siril_log(siril, "  [{}] {}".format(e["status"], e["path"].name))

        panels = [(e["prefix"], e["composite_suffix"], e["path"])
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
            siril.cmd("cd", _quote_if_needed(str(home_dir)))
        except Exception:
            pass
        siril.disconnect()


main()