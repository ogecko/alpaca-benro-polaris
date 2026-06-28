# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_4_Tiff.py
# Version: 4.0.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# Description
# -----------
# Converts every FITS file in result_fits/ to a 16-bit TIFF in result_tiff/.
# Uses astropy + tifffile directly for explicit pixel control.
#
# Orientation normalisation
# -------------------------
# PANO_MODE = "GALACTIC" (default):
#   The camera may be in portrait or landscape orientation -- we cannot
#   assume galactic longitude maps to pixel X or Y. Instead:
#
#   Pass 1: Compute the galactic orientation for every panel:
#     - glon_vec: 2D unit vector showing which pixel direction GLON increases
#     - glat_vec: 2D unit vector showing which pixel direction GLAT increases
#   Pass 2: Use the FIRST panel as the orientation reference. For each
#     subsequent panel, compute whether its galactic axes are consistent
#     with the reference. If GLON is flipped relative to reference, apply
#     an hflip or vflip (whichever axis GLON runs along) to normalise it.
#
#   This works correctly regardless of camera orientation (portrait/landscape)
#   and for panoramas spanning any arc length including >180 degrees.
#
# PANO_MODE = "RADEC":
#   Uses RA/Dec CD matrix determinant sign. Suitable for small RA/Dec panos.
#   Target: negative determinant (standard: East left, North up).
#
# PANO_MODE = "NONE":
#   No orientation normalisation. Use for AzAlt panos or when already consistent.
#
# FITS ROWORDER=BOTTOM-UP is always corrected to top-down raster order
# regardless of PANO_MODE.
#
# Usage
# -----
#   Make any final adjustments to result_fits/*.fits then run from Scripts menu.

import sirilpy as s
import traceback
from pathlib import Path

FITS_EXTENSIONS = {".fits", ".fit", ".fts"}

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
PANO_MODE = "GALACTIC"   # "GALACTIC" | "RADEC" | "NONE"

# Manual overrides for panels where VeraLux wrote incorrect metadata.
# List FITS stems (without extension) that need a forced flip regardless
# of what WCS or HISTORY says. Use when a panel stubbornly stitches wrong.
# Example: FORCE_VFLIP = ["GLAT007N_GLON360_2_LRGB_stretched_result"]
FORCE_VFLIP = []   # stems that need an extra vertical flip
FORCE_HFLIP = []   # stems that need an extra horizontal flip
# ---------------------------------------------------------------------------


def siril_log(siril, msg):
    safe = msg.encode("ascii", errors="replace").decode("ascii")
    if not safe.strip():
        safe = " "
    siril.log(safe)


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
    Count net horizontal and vertical flip operations recorded in FITS HISTORY.

    VeraLux uses inconsistent terminology across versions:
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
                 pano_mode, ref_glon_vec=None, ref_glat_vec=None,
                 target_det_sign=None):
    """
    Read a FITS, normalise orientation, write 16-bit TIFF.
    Returns (glon_vec, glat_vec) for use as reference by subsequent panels.
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

    roworder     = str(header.get('ROWORDER', 'BOTTOM-UP')).strip().upper()
    need_vflip   = False
    need_hflip   = False
    glon_vec     = glat_vec = None
    hist_hflip   = hist_vflip = False
    diag         = []   # collect diagnostic lines, print at end

    if pano_mode == "GALACTIC":
        glon_vec, glat_vec = galactic_orientation(header)
        hist_hflip, hist_vflip = count_mirror_ops(header)

        if glon_vec is not None:
            # Correct WCS vectors for net pixel flips VeraLux applied
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

            if ref_glon_vec is None:
                # This is the reference panel
                need_vflip = (glat_vec[1] > 0)
                need_hflip = False
                diag.append("  REFERENCE")
            else:
                # Compare to reference
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
              + "  vflip=" + str(need_vflip)
              + "  hflip=" + str(need_hflip))
    for d in diag:
        siril_log(siril, "  " + d)

    # Apply flips
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
        siril_log(siril, "Galactic_4_Tiff v4.0.0 connected.")
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

        # For GALACTIC mode: first panel sets the reference orientation
        # For RADEC mode: target is always negative determinant
        ref_glon_vec = ref_glat_vec = None
        target_det_sign = -1

        if PANO_MODE == "GALACTIC":
            siril_log(siril, "Reference orientation from first panel.")
            siril_log(siril, "All panels normalised to match reference.")
        elif PANO_MODE == "RADEC":
            siril_log(siril, "Target: negative CD matrix determinant.")
        else:
            siril_log(siril, "No orientation normalisation (PANO_MODE=NONE).")

        siril_log(siril, " ")

        ok = fail = 0
        hflipped = []
        for fits_path in fits_files:
            tiff_path = tiff_dir / (fits_path.stem + ".tif")
            try:
                glon_vec, glat_vec = fits_to_tiff(
                    fits_path, tiff_path, siril,
                    PANO_MODE, ref_glon_vec, ref_glat_vec,
                    target_det_sign)

                # First valid panel sets the reference.
                # If we vflipped it, invert dy components so subsequent
                # panels compare against the corrected orientation.
                if (PANO_MODE == "GALACTIC"
                        and ref_glon_vec is None
                        and glon_vec is not None):
                    need_vflip_ref = (glat_vec[1] > 0) if glat_vec else False
                    if need_vflip_ref:
                        ref_glon_vec = (glon_vec[0], -glon_vec[1])
                        ref_glat_vec = (glat_vec[0], -glat_vec[1])
                    else:
                        ref_glon_vec = glon_vec
                        ref_glat_vec = glat_vec
                    siril_log(siril, "  Reference set from: " + fits_path.stem[-44:])

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
            siril.cmd("cd", str(home_dir))
        except Exception:
            pass
        siril.disconnect()


main()