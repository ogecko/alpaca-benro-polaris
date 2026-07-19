# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_4_Tiff.py
# Version: 4.1.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# ==============================================================================
# OVERVIEW
# ==============================================================================
# Converts every FITS file in result_fits/ to a 16-bit TIFF in result_tiff/,
# ready for stitching. result_fits/ is never modified -- all corrections
# below only ever affect the exported TIFFs, so this script is always safe
# and cheap to re-run.
#
#   0. Green noise removal              (optional, RUN_REMOVE_GREEN_NOISE)
#   1. Cross-panel harmonization        (optional, RUN_HARMONIZE_PANELS)
#   2. Orientation normalisation        (PANO_MODE)
#   3. Export to 16-bit TIFF
#
# Orientation normalisation (PANO_MODE)
# --------------------------------------
# "GALACTIC" (default): the camera may be portrait or landscape, so galactic
#   longitude isn't guaranteed to map to a fixed pixel axis. The first panel
#   processed sets the orientation reference; every other panel is flipped
#   (horizontally and/or vertically) as needed to match it. Works for any
#   camera orientation and any panorama arc length, including >180 degrees.
#
# "RADEC": uses the WCS CD matrix determinant sign instead (target: negative,
#   i.e. East left / North up). Suited to small RA/Dec panoramas.
#
# "NONE": no orientation normalisation (e.g. Alt/Az panoramas, or when
#   already consistent).
#
# FITS ROWORDER=BOTTOM-UP is always corrected to top-down, regardless of mode.
#
# A panel shot in a different orientation to the rest of the mosaic (e.g.
# one taken in portrait while most are landscape, so GLON runs along its
# height instead of its width) gets an actual 90 degree rotation before
# flipping, not just hflip/vflip -- see RUN_AUTO_ROTATE.
#
# Usage
# -----
#   Make any final adjustments to result_fits/*.fits, then run from Scripts menu.

import sirilpy as s
import traceback
from pathlib import Path

FITS_EXTENSIONS = {".fits", ".fit", ".fts"}

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# ------------------------------------------------------------------------
# Step 0: Green noise removal -- RUN_REMOVE_GREEN_NOISE
# ------------------------------------------------------------------------
# Runs Siril's rmgreen (SCNR) on each panel before export. Green is
# essentially never a real deep-sky colour outside a few emission nebulae,
# so residual green after stretching a wideband RGB image is almost always
# noise or a calibration artefact.
RUN_REMOVE_GREEN_NOISE = False
GREEN_NOISE_TYPE = 0        # 0=average neutral, 1=maximum neutral,
                            # 2=maximum mask, 3=additive mask
GREEN_NOISE_AMOUNT = 1.0    # only used for type 2/3, range 0-1
GREEN_NOISE_PRESERVE_LIGHTNESS = True   # False passes -nopreserve to rmgreen

# ------------------------------------------------------------------------
# Step 1: Cross-panel harmonization -- RUN_HARMONIZE_PANELS
# ------------------------------------------------------------------------
# Evens out panel-to-panel colour/brightness differences that a stitcher's
# own blending can't fix, by nudging each panel's per-channel level to match
# the consensus across all panels. This is a mosaic-consistency correction,
# not a colour-accuracy one -- it deliberately trades absolute per-panel
# truth for a seamless-looking stitch.
RUN_HARMONIZE_PANELS = False

# How to characterise each panel's level per channel for cross-panel
# matching. "background_peak" (recommended) uses the same histogram-peak
# method the stretch step uses to find its own reference point, so it stays
# anchored to the true sky background regardless of how much nebulosity is
# in the panel. "median"/"mean" use whole-panel statistics instead, which is
# NOT recommended if panels vary a lot in how much nebulosity they contain --
# a panel with real extended emission can get that channel wrongly
# suppressed to match emptier neighbours.
HARMONIZE_STAT = "background_peak"   # "background_peak" | "median" | "mean"
HARMONIZE_PEAK_HIST_BINS = 3000      # histogram resolution for "background_peak"

# Clamp on the per-channel correction factor, so one very different panel
# (e.g. genuinely dominated by bright nebulosity) can't get pushed to an
# extreme correction. Gain is clipped to [1/HARMONIZE_MAX_GAIN, HARMONIZE_MAX_GAIN].
HARMONIZE_MAX_GAIN = 1.5

# ------------------------------------------------------------------------
# Step 2: Orientation normalisation
# ------------------------------------------------------------------------
PANO_MODE = "GALACTIC"   # "GALACTIC" | "RADEC" | "NONE"

# GALACTIC mode checks every panel against a fixed convention -- GLON
# increasing left, GLAT increasing up -- the same East-left/North-up sense
# RADEC mode targets. This is intentionally NOT taken from whichever panel
# happens to be processed first: a first-panel reference is only as
# reliable as that one panel's own orientation detection, and if it's
# wrong (e.g. a landscape panel that got misdetected), every other panel
# gets aligned to match the mistake instead of it being caught.
# Set True only if your project genuinely needs the opposite convention
# (GLON increasing right).
GALACTIC_MIRROR_CONVENTION = False

GALACTIC_REF_GLON_VEC = (1.0, 0.0) if GALACTIC_MIRROR_CONVENTION else (-1.0, 0.0)
GALACTIC_REF_GLAT_VEC = (0.0, -1.0)   # GLAT increasing up is not mirrored

# If a panel was shot in the opposite orientation to most of the mosaic
# (e.g. one panel taken in portrait while the rest are landscape, so GLON
# runs along its height instead of its width), hflip/vflip alone can't fix
# it -- flips only correct direction along whichever axis a coordinate
# already runs along, not which axis it runs along in the first place.
# RUN_AUTO_ROTATE detects this (GLON's dominant pixel axis doesn't match
# the fixed canonical convention) and rotates the panel 90 degrees before
# flipping, so every output TIFF ends up with a consistent width/height
# axis assignment regardless of how that panel was physically shot.
RUN_AUTO_ROTATE = True

# Manual overrides for panels where automatic orientation detection gets it
# wrong. List FITS stems (without extension) that need a forced flip
# regardless of what WCS/HISTORY says.
# Example: FORCE_VFLIP = ["GLAT007N_GLON360_2_LRGB_stretched_result"]
# This is an exact string match -- check the actual filename in result_fits/
# (stems include the exposure postfix, if Galactic_1/2's RUN_EXPOSURE_POSTFIX
# is enabled, e.g. "..._LRGB_1200s_stretched_result").
FORCE_VFLIP = []   # stems that need an extra vertical flip
FORCE_HFLIP = []   # stems that need an extra horizontal flip
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


def remove_green_noise(siril, src_path, dst_path):
    """
    Run Siril's rmgreen (SCNR) on src_path, saving the result to dst_path
    -- src_path is never modified, so result_fits/ stays pristine and this
    script can be re-run safely at any time.
    """
    if not cmd_safe(siril, "load", str(src_path)):
        return False

    rmgreen_args = ["rmgreen"]
    if not GREEN_NOISE_PRESERVE_LIGHTNESS:
        rmgreen_args.append("-nopreserve")
    rmgreen_args.append(str(GREEN_NOISE_TYPE))
    if GREEN_NOISE_TYPE in (2, 3):
        rmgreen_args.append(str(GREEN_NOISE_AMOUNT))

    if not cmd_safe(siril, *rmgreen_args):
        return False
    return cmd_safe(siril, "save", str(dst_path))


def _channel_histogram_peak(arr, n_bins=3000):
    """
    Find the background level as the peak (mode) of a fine histogram --
    the same method Galactic_3_Stretch.py uses to anchor its stretch
    curve. Stays correctly anchored to the true sky background regardless
    of how much bright nebulosity/dust is elsewhere in the panel, unlike
    a whole-panel median or mean (confirmed: a panel with real extended
    red emission got its R channel wrongly suppressed ~30% when matched
    on whole-panel median, since that statistic conflates "how much
    background sky is showing" with "how much real signal is in frame").
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


def compute_channel_stat(data, stat=HARMONIZE_STAT):
    """
    Characterise a panel's level per channel for harmonization.
    "background_peak" (default, recommended) anchors to the true sky
    background via a histogram peak, robust to how much real content
    (nebulosity, dust) is elsewhere in the panel. "median"/"mean" use
    whole-panel statistics instead -- NOT recommended if panels vary in
    how much nebulosity they contain (see HARMONIZE_STAT config comment).
    """
    import numpy as np
    n_ch = data.shape[0]
    stats = []
    for c in range(n_ch):
        if stat == "mean":
            stats.append(float(np.mean(data[c])))
        elif stat == "median":
            stats.append(float(np.median(data[c])))
        else:
            stats.append(_channel_histogram_peak(data[c], n_bins=HARMONIZE_PEAK_HIST_BINS))
    return stats


def galactic_orientation(header):
    """
    Compute 2D unit vectors for galactic longitude and latitude in pixel space.

    Returns (glon_vec, glat_vec) where each is (dx, dy) in pixel coordinates.
    dx > 0 means the coordinate increases to the right.
    dy > 0 means the coordinate increases downward (raster convention).

    Returns (None, None) if WCS is missing or computation fails.
    """
    try:
        import numpy as np
        from astropy.coordinates import SkyCoord
        import astropy.units as u

        ra0  = float(header['CRVAL1'])
        dec0 = float(header['CRVAL2'])

        # Image centre in galactic
        c0 = SkyCoord(ra=ra0*u.deg, dec=dec0*u.deg, frame='icrs')
        g0 = c0.galactic
        l0 = g0.l.deg
        b0 = g0.b.deg

        # Step in galactic longitude
        cl = SkyCoord(l=(l0 + 1.0)*u.deg, b=b0*u.deg, frame='galactic').icrs
        dra_l  = (cl.ra.deg - ra0) * np.cos(np.radians(dec0))
        ddec_l = cl.dec.deg - dec0

        # Step in galactic latitude
        cb = SkyCoord(l=l0*u.deg, b=(b0 + 1.0)*u.deg, frame='galactic').icrs
        dra_b  = (cb.ra.deg - ra0) * np.cos(np.radians(dec0))
        ddec_b = cb.dec.deg - dec0

        # Build CD matrix (pixel <- sky)
        if 'CD1_1' in header:
            cd11 = float(header['CD1_1']); cd12 = float(header['CD1_2'])
            cd21 = float(header['CD2_1']); cd22 = float(header['CD2_2'])
        elif 'CDELT1' in header or 'PC1_1' in header:
            d1 = float(header.get('CDELT1', 1.0))
            d2 = float(header.get('CDELT2', 1.0))
            cd11 = d1 * float(header.get('PC1_1', 1.0))
            cd12 = d1 * float(header.get('PC1_2', 0.0))
            cd21 = d2 * float(header.get('PC2_1', 0.0))
            cd22 = d2 * float(header.get('PC2_2', 1.0))
        else:
            return None, None

        # Inverse CD: sky offset -> pixel offset
        det = cd11 * cd22 - cd12 * cd21
        if abs(det) < 1e-20:
            return None, None

        def sky_to_pix(dra, ddec):
            dpx = ( cd22 * dra - cd12 * ddec) / det
            dpy = (-cd21 * dra + cd11 * ddec) / det
            mag = (dpx**2 + dpy**2) ** 0.5
            return (dpx / mag, dpy / mag) if mag > 1e-12 else (0.0, 0.0)

        glon_vec = sky_to_pix(dra_l, ddec_l)
        glat_vec = sky_to_pix(dra_b, ddec_b)
        return glon_vec, glat_vec

    except Exception:
        return None, None


def count_mirror_ops(header):
    """
    Count net horizontal and vertical flip operations recorded in FITS
    HISTORY -- for compatibility with files processed by an older version
    of this pipeline, whose HISTORY entries used varying terminology:
      Vertical flip:   'TOP-DOWN mirror'  OR  'Mirror Y'
      Horizontal flip: 'Mirror X'         OR  'Left-right mirror'

    Returns (net_hflip, net_vflip) as booleans:
      True  = odd number of that flip applied (net flip present)
      False = even number (flips cancel out)
    """
    n_vflip = 0
    n_hflip = 0
    for card in header.cards:
        if card.keyword != 'HISTORY':
            continue
        val = str(card.value).strip()
        # Vertical flip variants
        if 'TOP-DOWN' in val or 'Mirror Y' in val:
            n_vflip += 1
        # Horizontal flip variants
        if 'Mirror X' in val or 'Left-right mirror' in val:
            n_hflip += 1
    return (n_hflip % 2 == 1), (n_vflip % 2 == 1)


def cd_determinant(header):
    """Compute WCS CD matrix determinant for RADEC mode."""
    try:
        if 'CD1_1' in header:
            cd11 = float(header['CD1_1']); cd12 = float(header['CD1_2'])
            cd21 = float(header['CD2_1']); cd22 = float(header['CD2_2'])
        else:
            d1 = float(header.get('CDELT1', 1.0))
            d2 = float(header.get('CDELT2', 1.0))
            cd11 = d1 * float(header.get('PC1_1', 1.0))
            cd12 = d1 * float(header.get('PC1_2', 0.0))
            cd21 = d2 * float(header.get('PC2_1', 0.0))
            cd22 = d2 * float(header.get('PC2_2', 1.0))
        return cd11 * cd22 - cd12 * cd21
    except Exception:
        return None


def compute_flips(glon_vec, glat_vec, ref_glon_vec, ref_glat_vec):
    """
    Determine hflip/vflip needed to make this panel consistent with reference.

    Strategy:
    - Compute dot products of this panel's galactic vectors with the reference
    - If dot(glon_vec, ref_glon_vec) < 0: GLON is reversed relative to reference
    - If dot(glat_vec, ref_glat_vec) < 0: GLAT is reversed relative to reference
    - Determine which flip (h or v) fixes each reversal based on which pixel
      axis (X or Y) each galactic coordinate predominantly runs along
    """
    import numpy as np

    gx, gy = glon_vec
    bx, by = glat_vec
    rx, ry = ref_glon_vec
    rby_x, rby_y = ref_glat_vec

    glon_dot = gx * rx + gy * ry    # > 0 if same direction as reference
    glat_dot = bx * rby_x + by * rby_y

    glon_flipped = glon_dot < 0
    glat_flipped = glat_dot < 0

    if not glon_flipped and not glat_flipped:
        return False, False   # already consistent

    # Determine which pixel axis GLON runs along (X or Y)
    # |gx| vs |gy|: if |gx| > |gy| then GLON is more horizontal
    glon_is_horizontal = abs(gx) >= abs(gy)

    hflip = vflip = False

    if glon_flipped:
        if glon_is_horizontal:
            hflip = True   # GLON runs along X -- hflip fixes it
        else:
            vflip = True   # GLON runs along Y -- vflip fixes it

    if glat_flipped:
        # After glon fix, check if glat is still wrong
        # GLAT runs perpendicular to GLON
        glat_is_horizontal = abs(bx) >= abs(by)
        if glat_is_horizontal and not hflip:
            hflip = True
        elif not glat_is_horizontal and not vflip:
            vflip = True

    return hflip, vflip


def fits_to_tiff(fits_path, tiff_path, siril,
                 pano_mode, ref_glon_vec=GALACTIC_REF_GLON_VEC,
                 ref_glat_vec=GALACTIC_REF_GLAT_VEC,
                 target_det_sign=None, channel_gain=None):
    """
    Read a FITS, normalise orientation, write 16-bit TIFF.

    channel_gain, if given, is a list of per-channel multipliers applied
    right after reading the data (before flips/clipping) -- this is how
    the optional cross-panel harmonization correction gets applied.
    """
    import numpy as np
    from astropy.io import fits as _afits
    import tifffile

    with _afits.open(str(fits_path)) as hdul:
        header = hdul[0].header
        data   = hdul[0].data.copy().astype(np.float64)

    mono = data.ndim == 2
    if mono:
        data = data[np.newaxis]
    n_ch, H, W = data.shape

    if channel_gain is not None and len(channel_gain) == n_ch:
        for c in range(n_ch):
            data[c] = data[c] * channel_gain[c]

    roworder     = str(header.get('ROWORDER', 'BOTTOM-UP')).strip().upper()
    need_vflip   = False
    need_hflip   = False
    need_rotate  = False
    glon_vec     = glat_vec = None
    hist_hflip   = hist_vflip = False
    diag         = []   # collect diagnostic lines, print at end

    if pano_mode == "GALACTIC":
        glon_vec, glat_vec = galactic_orientation(header)
        hist_hflip, hist_vflip = count_mirror_ops(header)

        if glon_vec is not None:
            # Correct WCS vectors for net pixel flips recorded in HISTORY
            gx, gy = glon_vec
            bx, by = glat_vec
            if hist_hflip:
                gx, bx = -gx, -bx
            if hist_vflip:
                gy, by = -gy, -by
            glon_vec = (gx, gy)
            glat_vec = (bx, by)

            if hist_hflip or hist_vflip:
                diag.append("  hist_h=" + str(hist_hflip)
                            + " hist_v=" + str(hist_vflip)
                            + "  CORR glon=({:.3f},{:.3f})".format(*glon_vec)
                            + " glat=({:.3f},{:.3f})".format(*glat_vec))

            # If this panel's GLON runs predominantly along the vertical
            # pixel axis instead of horizontal (e.g. shot in portrait while
            # most of the mosaic is landscape), a 90 degree rotation is
            # needed before flipping -- flips alone can't swap which axis a
            # coordinate runs along, only its direction along that axis.
            if RUN_AUTO_ROTATE and abs(glon_vec[0]) < abs(glon_vec[1]):
                need_rotate = True
                # Vector transform matching a 90 deg CCW pixel rotation
                # (np.rot90, k=1): (x, y) -> (y, -x). Subsequent flip
                # determination then corrects any remaining sign mismatch,
                # regardless of which rotation direction was used here.
                glon_vec = (glon_vec[1], -glon_vec[0])
                glat_vec = (glat_vec[1], -glat_vec[0])
                diag.append("  ROTATE 90 -- GLON ran along vertical axis;"
                            + " rotated glon=({:.3f},{:.3f})".format(*glon_vec)
                            + " glat=({:.3f},{:.3f})".format(*glat_vec))

            # Every panel is checked against the same fixed reference
            # (GALACTIC_REF_GLON_VEC/GALACTIC_REF_GLAT_VEC by default) --
            # never against another panel -- so the result never depends
            # on processing order or on any one panel's own detection.
            glon_dot = glon_vec[0]*ref_glon_vec[0] + glon_vec[1]*ref_glon_vec[1]
            glat_dot = glat_vec[0]*ref_glat_vec[0] + glat_vec[1]*ref_glat_vec[1]
            diag.append("  DOT glon={:.3f} glat={:.3f}".format(glon_dot, glat_dot))
            need_hflip, need_vflip = compute_flips(
                glon_vec, glat_vec, ref_glon_vec, ref_glat_vec)
        else:
            # No WCS -- fall back to ROWORDER
            need_vflip = (roworder == 'BOTTOM-UP')
            diag.append("  No WCS -- ROWORDER=" + roworder)

    elif pano_mode == "RADEC":
        det = cd_determinant(header)
        if det is not None and target_det_sign is not None:
            need_hflip = (1 if det >= 0 else -1) != target_det_sign
        need_vflip = (roworder == 'BOTTOM-UP')
        diag.append("  det={:.6f}".format(det) if det else "  no WCS")

    else:
        need_vflip = (roworder == 'BOTTOM-UP')

    # Manual overrides (XOR toggle)
    stem = fits_path.stem
    if stem in FORCE_VFLIP:
        need_vflip = not need_vflip
        diag.append("  FORCE_VFLIP -> vflip=" + str(need_vflip))
    if stem in FORCE_HFLIP:
        need_hflip = not need_hflip
        diag.append("  FORCE_HFLIP -> hflip=" + str(need_hflip))

    # Log summary + all diagnostics together
    glon_str = ("({:.2f},{:.2f})".format(*glon_vec) if glon_vec else
                ("det" if pano_mode == "RADEC" else "none"))
    siril_log(siril, "  " + fits_path.stem[-44:]
              + "  " + glon_str
              + "  rotate=" + str(need_rotate)
              + "  vflip=" + str(need_vflip)
              + "  hflip=" + str(need_hflip))
    for d in diag:
        siril_log(siril, "  " + d)

    # Apply rotation (must match the vector transform used above: k=1 is
    # a 90 deg CCW pixel rotation), then flips
    if need_rotate:
        data = np.rot90(data, k=1, axes=(1, 2))
    if need_vflip:
        data = data[:, ::-1, :]
    if need_hflip:
        data = data[:, :, ::-1]

    data    = np.clip(data, 0.0, 1.0)
    data_16 = (data * 65535.0).astype(np.uint16)

    if n_ch >= 3:
        arr = np.transpose(data_16[:3], (1, 2, 0))
    else:
        arr = data_16[0]

    tifffile.imwrite(str(tiff_path), arr,
                     photometric='rgb' if n_ch >= 3 else 'minisblack')
    return glon_vec, glat_vec



def main():
    siril = s.SirilInterface()
    try:
        siril.connect()
        siril_log(siril, "Galactic_4_Tiff v4.1.0 connected.")
    except Exception as exc:
        print("Galactic_4_Tiff: could not connect: " + str(exc))
        return

    try:
        siril.cmd("requires", "1.4.0")
    except Exception:
        siril.error_messagebox("Galactic_4_Tiff requires Siril 1.4.0 or later.")
        siril.disconnect()
        return

    try:
        home_dir = Path(siril.get_siril_wd())
        fits_dir = home_dir / "result_fits"
        tiff_dir = home_dir / "result_tiff"

        siril_log(siril, "Home directory: " + str(home_dir))
        siril_log(siril, "PANO_MODE: " + PANO_MODE)

        if not fits_dir.is_dir():
            siril_log(siril, "[ERROR] result_fits/ not found.")
            siril.disconnect()
            return

        tiff_dir.mkdir(exist_ok=True)

        try:
            import sirilpy as _s
            _s.ensure_installed("tifffile")
            _s.ensure_installed("astropy")
        except Exception:
            pass

        fits_files = sorted(p for p in fits_dir.iterdir()
                            if p.is_file()
                            and p.suffix.lower() in FITS_EXTENSIONS)

        if not fits_files:
            siril_log(siril, "No FITS files found in result_fits/.")
            siril.disconnect()
            return

        siril_log(siril, "Converting " + str(len(fits_files)) + " file(s)...")
        siril_log(siril, "Note: result_fits/ is never modified -- green noise"
                  + " removal and harmonization (if enabled) only affect"
                  + " the exported result_tiff/ files, so re-running this"
                  + " script is always safe.")

        # ------------------------------------------------------------
        # Pass 0 (optional): green noise removal. Runs on a copy of each
        # panel in a working subdirectory -- result_fits/ originals are
        # never touched. effective_path maps each original fits_path to
        # the path fits_to_tiff should actually read from.
        # ------------------------------------------------------------
        effective_path = {p: p for p in fits_files}

        if RUN_REMOVE_GREEN_NOISE:
            siril_log(siril, " ")
            siril_log(siril, "Pass 0: removing green noise (rmgreen, type="
                      + str(GREEN_NOISE_TYPE) + ")...")
            green_dir = home_dir / "process" / "_tiff_green_noise_removed"
            green_dir.mkdir(parents=True, exist_ok=True)
            for fits_path in fits_files:
                dst = green_dir / fits_path.name
                if remove_green_noise(siril, fits_path, dst):
                    effective_path[fits_path] = dst
                    siril_log(siril, "  OK: " + fits_path.name)
                else:
                    siril_log(siril, "  [WARNING] rmgreen failed for "
                              + fits_path.name + " -- using original for this panel.")
        else:
            siril_log(siril, " ")
            siril_log(siril, "Pass 0: green noise removal skipped (RUN_REMOVE_GREEN_NOISE = False).")

        # ------------------------------------------------------------
        # Pass 1 (optional): cross-panel harmonization. Computes each
        # panel's per-channel level (post green-noise-removal, if that
        # ran) and nudges every panel toward the consensus across all
        # panels -- a mosaic-consistency correction, not a colour-
        # accuracy one. channel_gain_map stays empty (no correction) if
        # disabled.
        # ------------------------------------------------------------
        channel_gain_map = {}

        if RUN_HARMONIZE_PANELS:
            siril_log(siril, " ")
            siril_log(siril, "Pass 1: computing cross-panel harmonization ("
                      + HARMONIZE_STAT + ")...")
            import numpy as np
            from astropy.io import fits as _afits

            panel_stats = {}
            for fits_path in fits_files:
                src = effective_path[fits_path]
                try:
                    with _afits.open(str(src)) as hdul:
                        data = hdul[0].data.astype(np.float64)
                    if data.ndim == 2:
                        data = data[np.newaxis]
                    panel_stats[fits_path] = compute_channel_stat(data)
                except Exception as exc:
                    siril_log(siril, "  [WARNING] Could not read " + fits_path.name
                              + " for harmonization stats: " + str(exc))

            n_channels_seen = set(len(v) for v in panel_stats.values())
            if len(n_channels_seen) > 1:
                siril_log(siril, "  [WARNING] Panels have mixed channel counts "
                          + str(n_channels_seen) + " -- harmonization needs a"
                          + " consistent channel count across panels. Skipping.")
            elif panel_stats:
                n_ch = next(iter(n_channels_seen))
                reference = [
                    float(np.median([panel_stats[p][c] for p in panel_stats]))
                    for c in range(n_ch)
                ]
                siril_log(siril, "  Reference (consensus) level per channel: "
                          + ", ".join("{:.5f}".format(r) for r in reference))

                for fits_path, stats in panel_stats.items():
                    gains = []
                    for c in range(n_ch):
                        if stats[c] > 1e-9:
                            g = reference[c] / stats[c]
                        else:
                            g = 1.0
                        g = min(max(g, 1.0 / HARMONIZE_MAX_GAIN), HARMONIZE_MAX_GAIN)
                        gains.append(g)
                    channel_gain_map[fits_path] = gains
                    siril_log(siril, "  " + fits_path.stem[-44:] + "  gain="
                              + ", ".join("{:.3f}".format(g) for g in gains))
        else:
            siril_log(siril, " ")
            siril_log(siril, "Pass 1: harmonization skipped (RUN_HARMONIZE_PANELS = False).")

        # ------------------------------------------------------------
        # Main pass: orientation normalisation + TIFF export, reading
        # from effective_path (post green-noise-removal if that ran)
        # and applying any computed harmonization gain.
        # ------------------------------------------------------------
        siril_log(siril, " ")

        # For GALACTIC mode: every panel is checked against a fixed
        # canonical convention (GLON increasing left, GLAT increasing up --
        # the same East-left/North-up sense RADEC mode targets), rather
        # than against whichever panel happens to be processed first. A
        # reference taken from the first panel is only as reliable as that
        # one panel's own orientation detection; if it happens to be wrong
        # (e.g. a landscape panel that got misdetected), every other panel
        # gets aligned to match the mistake instead of the mistake being
        # caught. GALACTIC_MIRROR_CONVENTION flips this fixed convention if
        # your project genuinely needs the opposite sense.
        ref_glon_vec = GALACTIC_REF_GLON_VEC
        ref_glat_vec = GALACTIC_REF_GLAT_VEC
        target_det_sign = -1

        if PANO_MODE == "GALACTIC":
            siril_log(siril, "Reference: GLON increases "
                      + ("right" if GALACTIC_MIRROR_CONVENTION else "left")
                      + ", GLAT increases up (fixed convention, not panel-dependent).")
        elif PANO_MODE == "RADEC":
            siril_log(siril, "Target: negative CD matrix determinant.")
        else:
            siril_log(siril, "No orientation normalisation (PANO_MODE=NONE).")

        siril_log(siril, " ")

        ok = fail = 0
        for fits_path in fits_files:
            tiff_path = tiff_dir / (fits_path.stem + ".tif")
            src = effective_path[fits_path]
            gain = channel_gain_map.get(fits_path)
            try:
                glon_vec, glat_vec = fits_to_tiff(
                    src, tiff_path, siril,
                    PANO_MODE, ref_glon_vec, ref_glat_vec,
                    target_det_sign, channel_gain=gain)

                ok += 1
            except Exception as exc:
                siril_log(siril, "  [ERROR] " + fits_path.name + ": " + str(exc))
                fail += 1

        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "Galactic_4_Tiff complete.")
        siril_log(siril, "=" * 60)
        siril_log(siril, "  OK  : " + str(ok)
                  + "   FAIL: " + str(fail)
                  + "   TOTAL: " + str(ok + fail))
        siril_log(siril, "  TIFFs in result_tiff/ -- ready for stitching.")
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