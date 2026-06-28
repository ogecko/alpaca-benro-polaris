# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_0_Calibration.py
# Version: 1.0.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# Description
# -----------
# Performs calibration, preprocessing and GLAT/GLON renaming for all filter
# channels found under the Siril home directory.
#
# Expected directory structure:
#
#   <home>/
#     L/lights/         <- light frames (optional, any filter may be absent)
#     R/lights/
#     G/lights/
#     B/lights/
#     Ha/lights/
#     Sii/lights/
#     Oiii/lights/
#     calibration/
#       X/
#         darks/        <- darks (shared across all filters)
#         biases/       <- biases (shared across all filters)
#       L/flats/        <- per-filter flats (optional)
#       R/flats/
#       G/flats/
#       B/flats/
#       Ha/flats/
#       Sii/flats/
#       Oiii/flats/
#
# For each present filter this script:
#   1.  Scans and reports what is available (lights / flats / darks / biases)
#   2.  Builds master bias  (shared, built once)
#   3.  Builds master dark  (shared, calibrated with master bias)
#   4.  Builds master flat  (per-filter, calibrated with master bias)
#   5.  Preprocesses lights -> <filter>/process/pp_light_NNNNN.fits
#   6.  Plate-solves each pp_light_*.fits
#   7.  Renames pp_light_*.fits with GLAT/GLON prefix using the RA/Dec
#       from the FITS header (replaces fits_galactic.py)
#
# Output is ready for Galactic_1_Stack.py.
#
# Configuration
# -------------
# Edit the constants in the CONFIGURATION block below.

import sirilpy as s
import math
import traceback
from pathlib import Path
from collections import defaultdict

from astropy.io import fits as _afits
from astropy.coordinates import SkyCoord, Angle
import astropy.units as _u

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
# Filter directories to scan under home (order determines processing order)
FILTER_DIRS = ["L", "R", "G", "B", "Ha", "Sii", "Oiii"]

# Calibration root directory name
CALIB_DIR     = "calibration"
SHARED_DIR    = "X"          # subdirectory containing darks/ and biases/

# Subdirectory names within each filter/shared directory
LIGHTS_SUBDIR  = "lights"
FLATS_SUBDIR   = "flats"
DARKS_SUBDIR   = "darks"
BIASES_SUBDIR  = "biases"
PROCESS_SUBDIR = "process"

# Master calibration frame names (written into calibration/X/)
MASTER_BIAS_NAME = "master_bias"
MASTER_DARK_NAME = "master_dark"    # calibrated dark (bias subtracted)

# Master flat name written into calibration/<filter>/
MASTER_FLAT_NAME = "master_flat"

# Plate solving removed -- RA/Dec from capture software FITS headers
# is preserved through calibrate and used directly for GLAT/GLON rename.
# Full WCS plate solve is done by Galactic_2_Composite.py on the stack.

# GLAT/GLON rename settings (mirrors fits_galactic.py --rename behaviour)
PREFIX_LENGTH = 16          # characters in the prefix e.g. GLAT007N_GLON344
RENAME_DECIMALS = 0         # decimal places for prefix (integer gives 3+3 digits)

# RA/Dec header keyword candidates (tried in priority order)
RA_KEYS_DEG  = ["RA",      "RA_OBJ",  "CRVAL1"]
DEC_KEYS_DEG = ["DEC",     "DEC_OBJ", "CRVAL2"]
RA_KEYS_STR  = ["OBJCTRA"]
DEC_KEYS_STR = ["OBJCTDEC"]

FITS_EXTENSIONS = {".fits", ".fit", ".fts"}
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helpers
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


def count_fits(directory):
    """Return number of FITS files in directory, or 0 if directory absent."""
    if not directory or not directory.is_dir():
        return 0
    return sum(1 for p in directory.iterdir()
               if p.is_file() and p.suffix.lower() in FITS_EXTENSIONS)


# ---------------------------------------------------------------------------
# GLAT/GLON coordinate helpers (from fits_galactic.py)
# ---------------------------------------------------------------------------

def extract_ra_dec(header):
    """Pull RA/Dec from a FITS header. Returns (ra_deg, dec_deg) or None."""
    ra_deg = dec_deg = None
    for key in RA_KEYS_DEG:
        if key in header:
            try:
                ra_deg = float(header[key]); break
            except (ValueError, TypeError):
                pass
    for key in DEC_KEYS_DEG:
        if key in header:
            try:
                dec_deg = float(header[key]); break
            except (ValueError, TypeError):
                pass
    if ra_deg is None:
        for key in RA_KEYS_STR:
            if key in header:
                try:
                    ra_deg = Angle(str(header[key]), unit=_u.hourangle).deg; break
                except (ValueError, TypeError):
                    pass
    if dec_deg is None:
        for key in DEC_KEYS_STR:
            if key in header:
                try:
                    dec_deg = Angle(str(header[key]), unit=_u.degree).deg; break
                except (ValueError, TypeError):
                    pass
    if ra_deg is None or dec_deg is None:
        return None
    if not (0.0 <= ra_deg < 360.0) or not (-90.0 <= dec_deg <= 90.0):
        return None
    return ra_deg, dec_deg


def radec_to_galactic(ra_deg, dec_deg):
    """Convert equatorial J2000 to Galactic (l, b) in degrees via astropy."""
    c = SkyCoord(ra=ra_deg * _u.degree, dec=dec_deg * _u.degree, frame="icrs")
    g = c.galactic
    return g.l.deg % 360.0, g.b.deg


def find_glon_offset(glon_values):
    """
    Given a list of GLON values (0-359), find the offset to apply to each
    so that the values are monotonically increasing across the panorama.

    Algorithm: find the largest gap between consecutive values around the
    circle. The panel after that gap is the start of the panorama. Any
    panel whose GLON is less than the start value gets +360 added.

    Example: [318, 327, 335, 343, 351, 0, 8]
      Sorted: [0, 8, 318, 327, 335, 343, 351]
      Gaps (circular): 8, 310, 9, 8, 8, 8, 9  (gap from 351 back to 0 = 9)
      Largest gap: 310 (between 8 and 318) -> panorama starts at 318
      Result: 0->360, 8->368, rest unchanged
    """
    if not glon_values:
        return {}
    unique = sorted(set(glon_values))
    if len(unique) == 1:
        return {unique[0]: unique[0]}

    # Compute gaps between consecutive values (circular)
    gaps = []
    n = len(unique)
    for i in range(n):
        gap = (unique[(i + 1) % n] - unique[i]) % 360
        gaps.append((gap, i))

    # Largest gap -- the panorama starts at the value AFTER this gap
    largest_gap_idx = max(gaps, key=lambda x: x[0])[1]
    start_val = unique[(largest_gap_idx + 1) % n]

    # Build offset map: values before start_val (i.e. that wrapped) get +360
    result = {}
    for v in unique:
        if v < start_val:
            result[v] = v + 360
        else:
            result[v] = v
    return result


def make_glat_glon_prefix(b, glon_adjusted, decimals=0):
    """
    Build the GLAT/GLON filename prefix using wrap-corrected GLON.
    e.g. b=-7.123, glon_adjusted=368  ->  GLAT007S_GLON368_
    """
    ns = "S" if b < 0 else "N"
    glat_int = int(round(abs(b)))
    glon_int  = int(round(glon_adjusted))
    return "GLAT{:03d}{}_GLON{:03d}_".format(glat_int, ns, glon_int)


def rename_with_glat_glon(siril, process_dir):
    """
    Read each pp_light*.fits in process_dir and rename with GLAT/GLON prefix.
    GLON values are wrap-corrected so files sort monotonically across the
    panorama (e.g. 351->351, 0->360, 8->368 when the gap is at ~180°).
    Opens files read-only so Python doesn't hold a write lock during rename.
    Uses a retry loop for Windows file lock release timing after Siril closes.
    Returns (renamed_count, skipped_count, error_count).
    """
    import time as _time

    renamed = skipped = errors = 0
    pp_files = sorted(p for p in process_dir.iterdir()
                      if p.is_file()
                      and p.suffix.lower() in FITS_EXTENSIONS
                      and p.stem.startswith("pp_")
                      and not p.stem[:4].upper() == "GLAT")

    if not pp_files:
        return 0, 0, 0

    # Pass 1: read all coordinates to compute wrap-around offset
    file_coords = {}   # path -> (b, l_raw)
    glon_values = []
    for fits_path in pp_files:
        try:
            with _afits.open(str(fits_path), mode="readonly") as hdul:
                coords = extract_ra_dec(hdul[0].header)
        except Exception as exc:
            siril_log(siril, "  ERROR reading " + fits_path.name + ": " + str(exc))
            errors += 1
            continue
        if coords is None:
            siril_log(siril, "  SKIP (no RA/Dec): " + fits_path.name)
            skipped += 1
            continue
        ra_deg, dec_deg = coords
        l, b = radec_to_galactic(ra_deg, dec_deg)
        l_int = int(round(l)) % 360
        file_coords[fits_path] = (b, l, l_int)
        glon_values.append(l_int)

    # Compute wrap-corrected GLON mapping
    glon_offset_map = find_glon_offset(glon_values)
    if any(v != k for k, v in glon_offset_map.items()):
        adjusted = {k: v for k, v in glon_offset_map.items() if v != k}
        siril_log(siril, "  Wrap-around detected -- adjusting GLON values: "
                  + ", ".join(str(k) + "->" + str(v) for k, v in sorted(adjusted.items())))

    # Pass 2: rename with corrected GLON
    for fits_path, (b, l, l_int) in file_coords.items():
        glon_adjusted = glon_offset_map.get(l_int, l_int)
        prefix = make_glat_glon_prefix(b, glon_adjusted, RENAME_DECIMALS)
        new_path = fits_path.with_name(prefix + fits_path.name)

        # Retry rename up to 5 times -- Windows releases Siril's file lock
        # asynchronously after close/cd, so a short wait may be needed
        for attempt in range(5):
            try:
                if new_path.exists():
                    new_path.unlink()
                fits_path.rename(new_path)
                renamed += 1
                break
            except OSError as exc:
                if attempt < 4:
                    _time.sleep(0.5)
                else:
                    siril_log(siril, "  ERROR renaming " + fits_path.name
                              + ": " + str(exc))
                    errors += 1

    return renamed, skipped, errors


# ---------------------------------------------------------------------------
# Master calibration builders
# All intermediate files (numbered FITS from convert, pp_ sequences) go into
# a process/ subdirectory so the originals stay clean and re-runs don't
# pick up stacked results as inputs.
# ---------------------------------------------------------------------------

def build_master_bias(siril, biases_dir, output_dir):
    """
    Convert biases into process/, stack to master_bias in output_dir.
    Returns path to master bias file, or None on failure.
    """
    siril_log(siril, "  Building master bias from " + str(biases_dir) + "...")
    proc = biases_dir / "process"
    proc.mkdir(exist_ok=True)
    # Convert originals into process/ to keep biases/ clean
    if not cmd_safe(siril, "cd", str(biases_dir)):
        return None
    if not cmd_safe(siril, "convert", "bias", "-out=" + str(proc)):
        return None
    if not cmd_safe(siril, "cd", str(proc)):
        return None
    # Force 32-bit to handle mixed-precision input files
    cmd_safe(siril, "set32bits")
    # Use sigma-rejection matching the official Mono_Preprocessing.ssf
    if not cmd_safe(siril, "stack", "bias", "rej", "3", "3", "-nonorm",
                    "-out=" + MASTER_BIAS_NAME):
        return None
    for ext in (".fits", ".fit", ".fts"):
        f = proc / (MASTER_BIAS_NAME + ext)
        if f.exists():
            dest = output_dir / (MASTER_BIAS_NAME + ext)
            import shutil
            shutil.copy2(f, dest)
            siril_log(siril, "  Master bias: " + dest.name)
            return dest
    siril_log(siril, "  [ERROR] Master bias file not found after stacking.")
    return None


def build_master_dark(siril, darks_dir, master_bias_path, output_dir):
    """
    Convert darks into process/, calibrate with bias, stack to master_dark.
    Returns path to master dark file, or None on failure.
    """
    siril_log(siril, "  Building master dark from " + str(darks_dir) + "...")
    proc = darks_dir / "process"
    proc.mkdir(exist_ok=True)
    if not cmd_safe(siril, "cd", str(darks_dir)):
        return None
    if not cmd_safe(siril, "convert", "dark", "-out=" + str(proc)):
        return None
    if not cmd_safe(siril, "cd", str(proc)):
        return None
    # Stack raw darks WITHOUT subtracting bias -- this matches the official
    # Mono_Preprocessing.ssf. The dark retains its bias signal, which is
    # correct: when calibrating lights, the dark (bias+thermal) is subtracted
    # from the light (bias+thermal+signal), cancelling both bias and dark.
    # Subtracting bias from darks first would leave bias uncorrected in lights.
    if not cmd_safe(siril, "stack", "dark", "rej", "3", "3", "-nonorm",
                    "-out=" + MASTER_DARK_NAME):
        return None
    for ext in (".fits", ".fit", ".fts"):
        f = proc / (MASTER_DARK_NAME + ext)
        if f.exists():
            dest = output_dir / (MASTER_DARK_NAME + ext)
            import shutil
            shutil.copy2(f, dest)
            siril_log(siril, "  Master dark: " + dest.name)
            return dest
    siril_log(siril, "  [ERROR] Master dark file not found after stacking.")
    return None


def build_master_flat(siril, flats_dir, master_bias_path, filter_name):
    """
    Convert flats into process/, calibrate with bias, stack to master_flat.
    Master flat is written into flats_dir/ (not process/) so it is easy
    to find and inspect.
    Returns path to master flat file, or None on failure.
    """
    siril_log(siril, "  Building master flat for " + filter_name
              + " from " + str(flats_dir) + "...")
    proc = flats_dir / "process"
    proc.mkdir(exist_ok=True)
    if not cmd_safe(siril, "cd", str(flats_dir)):
        return None
    if not cmd_safe(siril, "convert", "flat", "-out=" + str(proc)):
        return None
    if not cmd_safe(siril, "cd", str(proc)):
        return None
    if master_bias_path and master_bias_path.exists():
        if not cmd_safe(siril, "calibrate", "flat",
                        "-bias=" + str(master_bias_path)):
            return None
        flat_seq = "pp_flat"
    else:
        siril_log(siril, "  No master bias -- stacking raw flats.")
        flat_seq = "flat"
    # Write master flat to flats_dir (parent of process/) for easy access
    master_flat_path = flats_dir / MASTER_FLAT_NAME
    # Use sigma-rejection matching the official Mono_Preprocessing.ssf
    if not cmd_safe(siril, "stack", flat_seq, "rej", "3", "3", "-norm=mul",
                    "-out=" + str(master_flat_path)):
        return None
    for ext in (".fits", ".fit", ".fts"):
        f = flats_dir / (MASTER_FLAT_NAME + ext)
        if f.exists():
            siril_log(siril, "  Master flat: " + f.name)
            return f
    siril_log(siril, "  [ERROR] Master flat file not found after stacking.")
    return None



# ---------------------------------------------------------------------------
# Per-filter light preprocessing
# ---------------------------------------------------------------------------

def preprocess_filter(siril, filter_name, lights_dir, process_dir,
                      master_bias_path, master_dark_path, master_flat_path):
    """
    Preprocess lights for one filter.
    Output goes to process_dir as pp_light_NNNNN.fits.
    Returns True on success.
    """
    siril_log(siril, "  Preprocessing " + filter_name + " lights...")
    process_dir.mkdir(parents=True, exist_ok=True)

    # Convert lights directly into process_dir so the sequence is there.
    # calibrate must run from the same directory as the sequence.
    if not cmd_safe(siril, "cd", str(lights_dir)):
        return False
    if not cmd_safe(siril, "convert", "light", "-out=" + str(process_dir)):
        return False

    # cd to process_dir -- calibrate reads and writes from CWD
    if not cmd_safe(siril, "cd", str(process_dir)):
        return False

    # Build calibrate command following official Mono_Preprocessing.ssf exactly:
    #   calibrate light -dark=dark_stacked -flat=pp_flat_stacked -cc=dark
    #
    # No -bias= (bias is inside the raw dark, double-subtraction otherwise)
    # No -opt  (only for mismatched library darks, official script omits it)
    # -cc=dark enables cosmetic correction: hot pixels in the master dark
    #   (sigma=3) are replaced in each light frame. The official script
    #   shows: "Cosmetic correction from masterdark: using sigma 3.00 for
    #   hot pixels. 953 corrected pixels". Without this, hot pixels remain
    #   as white specks in calibrated images.
    pp_args = ["calibrate", "light"]
    if master_dark_path and master_dark_path.exists():
        pp_args.append("-dark=" + str(master_dark_path))
        pp_args.append("-cc=dark")   # hot pixel cosmetic correction from dark
    if master_flat_path and master_flat_path.exists():
        pp_args.append("-flat=" + str(master_flat_path))
    # prefix=pp_ gives pp_light_00001.fits (sequence name "light" appended by Siril)
    pp_args.append("-prefix=pp_")

    if not cmd_safe(siril, *pp_args):
        siril_log(siril, "  [ERROR] Preprocessing failed for " + filter_name)
        return False

    n_out = count_fits(process_dir)
    siril_log(siril, "  " + filter_name + ": " + str(n_out)
              + " calibrated frames in " + PROCESS_SUBDIR + "/")
    return True



def main():
    siril = s.SirilInterface()

    try:
        siril.connect()
        siril_log(siril, "Galactic_0_Calibration v1.0.0 connected.")
    except Exception as exc:
        print("Galactic_0_Calibration: could not connect: " + str(exc))
        return

    try:
        siril.cmd("requires", "1.4.0")
    except Exception:
        siril.error_messagebox(
            "Galactic_0_Calibration requires Siril 1.4.0 or later.")
        siril.disconnect()
        return

    try:
        home_dir = Path(siril.get_siril_wd())
        siril_log(siril, "Home directory: " + str(home_dir))

        # ------------------------------------------------------------------
        # Step 1: Scan and report availability
        # ------------------------------------------------------------------
        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "Scanning directory structure...")
        siril_log(siril, "=" * 60)

        calib_root  = home_dir / CALIB_DIR
        shared_dir  = calib_root / SHARED_DIR
        darks_dir   = shared_dir / DARKS_SUBDIR
        biases_dir  = shared_dir / BIASES_SUBDIR

        n_darks  = count_fits(darks_dir)
        n_biases = count_fits(biases_dir)

        siril_log(siril, "Calibration frames (shared):")
        siril_log(siril, "  Biases : " + str(n_biases)
                  + "  (" + str(biases_dir) + ")")
        siril_log(siril, "  Darks  : " + str(n_darks)
                  + "  (" + str(darks_dir) + ")")

        # Scan each filter
        filter_info = {}   # filter -> { lights, flats, lights_dir, flats_dir, process_dir }
        siril_log(siril, " ")
        siril_log(siril, "Filter summary:")
        siril_log(siril, "  {:<8} {:>8} {:>8}".format("Filter", "Lights", "Flats"))
        siril_log(siril, "  " + "-" * 30)
        for filt in FILTER_DIRS:
            lights_dir  = home_dir / filt / LIGHTS_SUBDIR
            process_dir = home_dir / filt / PROCESS_SUBDIR
            flats_dir   = calib_root / filt / FLATS_SUBDIR
            n_lights = count_fits(lights_dir)
            n_flats  = count_fits(flats_dir)
            if n_lights == 0:
                continue   # filter not present
            filter_info[filt] = {
                "lights_dir":  lights_dir,
                "process_dir": process_dir,
                "flats_dir":   flats_dir if n_flats > 0 else None,
                "n_lights":    n_lights,
                "n_flats":     n_flats,
            }
            flats_str = str(n_flats) if n_flats > 0 else "NONE"
            siril_log(siril, "  {:<8} {:>8} {:>8}".format(
                filt, n_lights, flats_str))

        if not filter_info:
            siril_log(siril, "No light frames found in any filter directory.")
            siril.disconnect()
            return

        siril_log(siril, " ")
        siril_log(siril, str(len(filter_info)) + " filter(s) to process: "
                  + ", ".join(filter_info.keys()))

        # ------------------------------------------------------------------
        # Step 2: Build shared master bias and master dark (once)
        # ------------------------------------------------------------------
        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "Building shared calibration masters...")
        siril_log(siril, "=" * 60)

        master_bias_path = None
        master_dark_path = None

        if n_biases > 0:
            master_bias_path = build_master_bias(siril, biases_dir, shared_dir)
        else:
            siril_log(siril, "  No biases -- skipping master bias.")

        if n_darks > 0:
            master_dark_path = build_master_dark(
                siril, darks_dir, master_bias_path, shared_dir)
        else:
            siril_log(siril, "  No darks -- skipping master dark.")

        # ------------------------------------------------------------------
        # Steps 3-7: Per-filter processing
        # ------------------------------------------------------------------
        ok_filters = []
        fail_filters = []
        filter_renamed = {}  # filt -> count of renamed files

        for filt, info in filter_info.items():
            siril_log(siril, " ")
            siril_log(siril, "=" * 60)
            siril_log(siril, "Filter: " + filt + "  ("
                      + str(info["n_lights"]) + " lights, "
                      + str(info["n_flats"]) + " flats)")
            siril_log(siril, "=" * 60)

            # Step 3: Master flat (per filter)
            master_flat_path = None
            if info["flats_dir"]:
                master_flat_path = build_master_flat(
                    siril, info["flats_dir"], master_bias_path, filt)
                if not master_flat_path:
                    siril_log(siril, "  [WARNING] Master flat failed -- "
                              + "continuing without flat correction.")
            else:
                siril_log(siril, "  No flats for " + filt
                          + " -- continuing without flat correction.")

            # Step 4: Preprocess lights
            ok = preprocess_filter(
                siril, filt,
                info["lights_dir"],
                info["process_dir"],
                master_bias_path,
                master_dark_path,
                master_flat_path,
            )
            if not ok:
                fail_filters.append(filt)
                continue

            # Step 5: Rename with GLAT/GLON prefix
            # RA/Dec is preserved in pp_light headers from the original
            # capture software -- no plate solve needed before renaming.
            # cd to home_dir first, then close -- on Windows, moving away
            # from the directory before closing releases file locks reliably.
            siril_log(siril, "  [5] Renaming with GLAT/GLON prefix...")
            # Release Siril file locks before renaming:
            # 1. cd away from the process directory
            # 2. close the current image
            # 3. brief sleep to let Windows release handles
            cmd_safe(siril, "cd", str(home_dir))
            cmd_safe(siril, "close")
            renamed, skipped, errors = rename_with_glat_glon(
                siril, info["process_dir"])
            siril_log(siril, "  Renamed: " + str(renamed)
                      + "  Skipped: " + str(skipped)
                      + "  Errors: " + str(errors))
            filter_renamed[filt] = renamed

            ok_filters.append(filt)

        # Restore home directory
        cmd_safe(siril, "cd", str(home_dir))

        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "Galactic_0_Calibration complete.")
        siril_log(siril, "=" * 60)
        siril_log(siril, "  Darks   : " + str(n_darks)
                  + "  Biases: " + str(n_biases))
        siril_log(siril, "  Master bias: "
                  + (str(master_bias_path.name) if master_bias_path else "not built"))
        siril_log(siril, "  Master dark: "
                  + (str(master_dark_path.name) if master_dark_path else "not built"))
        siril_log(siril, " ")
        siril_log(siril, "  {:<8} {:>8} {:>8} {:>10} {:>8}".format(
                  "Filter", "Lights", "Flats", "Calibrated", "Renamed"))
        siril_log(siril, "  " + "-" * 48)
        for filt in ok_filters:
            info = filter_info[filt]
            # Count calibrated files: pp_light_* before rename, GLAT*_pp_light_* after
            n_cal = sum(1 for p in info["process_dir"].iterdir()
                        if p.is_file()
                        and p.suffix.lower() in {".fits", ".fit", ".fts"}
                        and ("pp_light_" in p.stem or p.stem.startswith("pp_")))
            n_ren = filter_renamed.get(filt, 0)
            siril_log(siril, "  {:<8} {:>8} {:>8} {:>10} {:>8}".format(
                      filt, info["n_lights"], info["n_flats"], n_cal, n_ren))
        for filt in fail_filters:
            siril_log(siril, "  {:<8}   FAILED".format(filt))
        siril_log(siril, " ")
        siril_log(siril, "  Filters OK    : " + (", ".join(ok_filters) if ok_filters else "none"))
        siril_log(siril, "  Filters failed: " + (", ".join(fail_filters) if fail_filters else "none"))
        siril_log(siril, "  Next: run Galactic_1_Stack.py")
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