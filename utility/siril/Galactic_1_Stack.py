# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_1_Stack.py
# Version: 1.3.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# ==============================================================================
# OVERVIEW
# ==============================================================================
# Renames each channel's calibrated lights with a GLAT/GLON panel prefix
# (Step 0), then groups them by that prefix (see extract_panel_prefix --
# the GLAT.../GLON..._ label itself, decimals and all, not a fixed
# character count) and for every group:
#
#   1. Converts the group's files into a Siril sequence
#   2. Registers the sequence (global star alignment)
#   3. Stacks with sigma-clipping rejection
#   4. Deconvolves with BlurXTerminator              (optional, RUN_BLURXTERMINATOR)
#   5. Denoises with RC-Astro NoiseXTerminator        (optional, RUN_NOISEXTERMINATOR)
#   6. Denoises with GraXpert                         (optional, RUN_DENOISE)
#   7. Runs aberration correction                    (optional, RUN_ABERRATION_REMOVER)
#   8. Saves as <prefix>_<channel>_stack[_NNNs].fits
#
# BlurXTerminator runs before either denoise step (step 4, ahead of steps
# 5-6) because deconvolution wants the cleanest, most detailed data it can
# get and can amplify residual noise -- both denoise tools then clean that
# up afterwards. NoiseXTerminator and GraXpert are independent switches
# that can both be on at once (NXT then GraXpert), either alone, or
# neither -- most setups only need one, so leaving both on is usually
# redundant rather than complementary.
#
# Output goes to <channel>/stacked/, ready for Galactic_2_Composite.py.
#
# If your calibrated lights have no RA/Dec (e.g. capture software that
# doesn't record it, or a camera RAW format like CR3 with nowhere to store
# a plate-solve solution), plate-solve the FITS files in each
# <channel>/process/ directory (e.g. with ASTAP's bulk solve) before running
# this script -- Step 0 reads CRVAL1/CRVAL2 (WCS) as well as dedicated
# RA/Dec keywords, so a plate-solved file works either way. Individual
# subs are often too short/noisy for ASTAP to solve at all, even when a
# stack of them would solve fine -- files where no RA/Dec can be found are
# grouped into one "unsolved" stack per channel instead (RUN_GROUP_UNSOLVED),
# rather than each becoming its own single-frame group.
#
# IMPORTANT for Galactic_2_Composite.py: that script groups its own input
# (this script's _stack output files) the same way, via its own copy of
# extract_panel_prefix() -- if you ever change how panel prefixes are
# built here, mirror the change there too, or panels will silently stop
# lining up between the two scripts.
#
# Prerequisites
# -------------
#   Siril 1.4.0 or later.
#   GraXpert-AI.py installed via Scripts -> Get Scripts (if RUN_DENOISE).
#   GraXpert executable path set in Preferences -> Miscellaneous.
#   BlurXTerminator.py installed via Scripts -> Get Scripts, the RC-Astro
#   stand-alone CLI tool installed, and your BlurXTerminator license
#   activated (if RUN_BLURXTERMINATOR).
#   NoiseXTerminator.py installed via Scripts -> Get Scripts, the same
#   RC-Astro CLI tool, and your NoiseXTerminator license activated (if
#   RUN_NOISEXTERMINATOR).
#   Run Galactic_0_Calibration.py first.

import sirilpy as s
import os
import re
import traceback
from pathlib import Path
from collections import defaultdict

from astropy.io import fits as _afits
from astropy.coordinates import SkyCoord, Angle
import astropy.units as _u

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# ------------------------------------------------------------------------
# Directory layout
# ------------------------------------------------------------------------
# Channel subdirectories to scan (relative to Siril home directory). Stacked
# outputs are saved back into the same directory they were found in. Only
# directories that exist are processed -- missing filters are skipped.
CHANNEL_DIRS = ["L/stacked", "R/stacked", "G/stacked", "B/stacked",
                "Ha/stacked", "Sii/stacked", "Oiii/stacked", "OSC/stacked"]

FITS_EXTENSIONS = {".fits", ".fit", ".fts"}

# ------------------------------------------------------------------------
# Step 0: GLAT/GLON panel renaming
# ------------------------------------------------------------------------
# Renames each channel's calibrated lights (<channel>/process/pp_light_*.fits,
# from Galactic_0_Calibration.py) with a GLAT/GLON panel prefix, computed
# from each file's own RA/Dec header -- this is what determines which subs
# get grouped into the same panel below. Runs here rather than in
# Galactic_0_Calibration.py so you can batch plate-solve the calibrated
# FITS files in between (e.g. with ASTAP) if your capture software didn't
# record RA/Dec -- a camera RAW format like Canon's CR3 has nowhere to
# store a plate-solve solution, but the calibrated FITS output does.

# Rounding precision for the panel label. 0 = nearest whole degree. Negative
# values round to a coarser unit (-1 = nearest 10 degrees) -- use this if subs
# from the same panel are landing on opposite sides of a rounding boundary.
# Positive values keep decimal places for finer-grained panels -- IMPORTANT:
# unlike earlier versions of this script, the decimal places are now encoded
# directly into the GLAT/GLON filename label (e.g. decimals=1 ->
# "GLAT007.2S_GLON344.5_"), not silently discarded. This matters whenever
# your mosaic's row/column spacing is small relative to the sensor's own
# FOV on that axis (e.g. a long-focal-length setup with sub-1-degree FOV
# and ~0.7 degree dithered row spacing) -- with decimals=0, two genuinely
# different rows could round to the very same whole-degree label and get
# wrongly merged into one group, which then register/stacks to only their
# thin sliver of common overlap instead of two full-size separate panels.
# If your panels are landing on opposite sides of a rounding boundary AND
# genuinely different panels are colliding at low precision, raise
# RENAME_DECIMALS (e.g. to 1) before reaching for MERGE_LABELS.
RENAME_DECIMALS = -1

# Manual override for one-off anomalies (e.g. a mount slip put two batches of
# the same intended panel further apart than any RENAME_DECIMALS setting could
# safely group without also merging genuinely separate panels elsewhere).
# Maps a generated prefix (including its trailing underscore) to the prefix
# you want instead, e.g.:
#   MERGE_LABELS = {"GLAT007N_GLON123_": "GLAT007N_GLON120_"}
# or, with RENAME_DECIMALS > 0:
#   MERGE_LABELS = {"GLAT007.2N_GLON123.4_": "GLAT007.2N_GLON120.1_"}
# Check the Siril log for the exact generated prefixes. Leave {} if not needed.
MERGE_LABELS = {}

# RA/Dec header keywords, tried in priority order. CRVAL1/CRVAL2 (WCS) are
# included so a plate-solved file works even without dedicated RA/Dec keys.
RA_KEYS_DEG  = ["RA", "RA_OBJ", "CRVAL1"]
DEC_KEYS_DEG = ["DEC", "DEC_OBJ", "CRVAL2"]
RA_KEYS_STR  = ["OBJCTRA"]
DEC_KEYS_STR = ["OBJCTDEC"]

# If True, files with no RA/Dec (e.g. individual subs too short/noisy for
# ASTAP to solve, common for DSLR exposures) are grouped into a single
# "unsolved" stack per channel instead of being left unrenamed (which
# previously meant each one became its own single-frame group, since an
# unrenamed "pp_light_NNNNN.fits" has a different filename prefix for
# every N). Set False to restore skip-and-leave-unrenamed behaviour.
RUN_GROUP_UNSOLVED = True
UNSOLVED_PREFIX = "UNSOLVED_PANEL__"   # matched as a literal prefix by
                                       # extract_panel_prefix() below, so
                                       # every unsolved file groups together
                                       # regardless of its original name

# ------------------------------------------------------------------------
# Step 2: Registration
# ------------------------------------------------------------------------
REGISTER_TRANSF = "homography"   # shift / similarity / affine / homography

# STACK_FRAMING="min" crops each group to the common overlap area across all
# its subs before stacking, removing the ragged partial-coverage borders that
# dithering leaves at the edges. "current" disables this (single-pass
# register, no cropping).
#
# If a group has accumulated enough drift that no single region is shared by
# every frame (common on a long, undithered session), "min" automatically
# falls back to no cropping for that group rather than failing it entirely.
STACK_FRAMING = "min"   # "min" | "current"

# ------------------------------------------------------------------------
# Step 3: Stacking
# ------------------------------------------------------------------------
STACK_TYPE       = "rej"        # stacking type (rej = sigma-clipping rejection)
STACK_SIGMA_LOW  = 3            # lower sigma threshold for rejection
STACK_SIGMA_HIGH = 3            # upper sigma threshold for rejection
STACK_NORM       = "addscale"   # normalisation: addscale / add / mul / no

# ------------------------------------------------------------------------
# Step 4: BlurXTerminator deconvolution -- RUN_BLURXTERMINATOR
# ------------------------------------------------------------------------
# Runs RC-Astro's BlurXTerminator (via its Siril script, same mechanism as
# GraXpert-AI.py below) on the stack right after stacking and before
# denoise. Requires the RC-Astro stand-alone CLI tool and an activated
# BlurXTerminator license (see Prerequisites above) -- Siril's own
# BlurXTerminator.py script just drives that CLI tool under the hood.
#
# Config names and CLI flags below match Galactic_3_Stretch.py's own
# BXT_* config/_build_bxt_args() exactly (that script also calls
# BlurXTerminator.py) -- keep the two in sync if RC-Astro ever renames a
# flag again (it has happened before: --ansr became --ansp).
RUN_BLURXTERMINATOR = False

BXT_SHARPEN_STARS      = 0.0     # --ss    (0.0 - 0.7)
BXT_ADJUST_STAR_HALOS  = 0.0     # --ash   (-0.5 - 0.5)
BXT_AUTOMATIC_PSF      = True    # --ansp / --no-ansp (Auto Nonstellar PSF)
BXT_SHARPEN_NONSTELLAR = 0.5     # --sn    (0.0 - 1.0)
BXT_CORRECT_ONLY       = False   # --correct-only; when True every other
                                  # BXT_* setting above is ignored (pinned
                                  # by the tool itself) and only PSF
                                  # aberration correction is applied.
# Only used if BXT_AUTOMATIC_PSF is False (manual nonstellar PSF diameter,
# in pixels, 0.0 - 8.0):
BXT_NONSTELLAR_RADIUS = 0.0

# ------------------------------------------------------------------------
# Step 5: RC-Astro NoiseXTerminator -- RUN_NOISEXTERMINATOR
# ------------------------------------------------------------------------
# Runs after BlurXTerminator, via `pyscript NoiseXTerminator.py`. Requires
# the same RC-Astro stand-alone CLI tool as BlurXTerminator above,
# licensed separately (see Prerequisites).
#
# Config names and CLI flags below match Galactic_3_Stretch.py's own
# NXT_* config/_build_nxt_args() exactly (that script also calls
# NoiseXTerminator.py) -- keep the two in sync if RC-Astro ever changes
# a flag name.
RUN_NOISEXTERMINATOR = False

NXT_DENOISE    = 0.9   # --dn (0.0 - 1.0)
NXT_ITERATIONS = 2     # --it (1 - 5)
# Color Separation / Frequency Separation are GUI-only switches in
# NoiseXTerminator's own schema -- RC-Astro doesn't expose a CLI flag for
# them, so they are always off when run headless via pyscript regardless
# of these values. Kept here as documentation of the intended (and only
# reachable) setting.
NXT_COLOR_SEPARATION     = False
NXT_FREQUENCY_SEPARATION = False

# ------------------------------------------------------------------------
# Step 6: Denoise -- RUN_DENOISE
# ------------------------------------------------------------------------
RUN_DENOISE      = False
DENOISE_STRENGTH = 1.0     # GraXpert denoising strength: 0.0 (none) to 1.0 (max)

# ------------------------------------------------------------------------
# Step 7: Aberration correction -- RUN_ABERRATION_REMOVER
# ------------------------------------------------------------------------
# Opens a GUI dialog for each panel group -- only enable when you need to
# correct specific panels (delete their _stack file and rerun with this on).
# Leave False for normal automated runs.
RUN_ABERRATION_REMOVER = False

# ------------------------------------------------------------------------
# Step 8: Save / naming -- RUN_EXPOSURE_POSTFIX
# ------------------------------------------------------------------------
# Appends the total summed exposure time to stack filenames, e.g. 10x30s subs
# -> "..._stack_300s.fits". Sums each input file's own exposure header (not
# count x nominal value, so it's correct even with mixed exposure times).
# EXPOSURE_KEYS lists the header keywords tried, in order, since different
# capture software uses different names.
RUN_EXPOSURE_POSTFIX = True
EXPOSURE_KEYS = ["EXPTIME", "EXPOSURE", "EXPTIME1"]
# ==============================================================================


def siril_log(siril, msg):
    """Write a plain-ASCII message to the Siril log.
    siril.log() already echoes to the Siril console -- no print() needed.
    Empty strings crash the pipe protocol, so replace them with a space.
    """
    safe = msg.encode("ascii", errors="replace").decode("ascii")
    if not safe:
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
    """
    Run a Siril command, returning True on success, False on failure.
    Errors are logged but never re-raised, so the loop continues.
    """
    args = tuple(_quote_if_needed(a) for a in args)
    try:
        siril.cmd(*args)
        return True
    except Exception as exc:
        siril_log(siril, "  [WARNING] Command failed: " + " ".join(str(a) for a in args))
        siril_log(siril, "            " + str(exc))
        return False


# ---------------------------------------------------------------------------
# GLAT/GLON panel renaming (Step 0)
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


def round_coord(value, decimals):
    """
    Round a coordinate to RENAME_DECIMALS places. Negative decimals round
    to a coarser unit (e.g. -1 -> nearest 10), which is the main lever for
    fixing subs of the same intended panel landing on opposite sides of a
    rounding boundary -- see the RENAME_DECIMALS config comment.
    """
    return round(value, decimals)


def radec_to_galactic(ra_deg, dec_deg):
    """Convert equatorial J2000 to Galactic (l, b) in degrees via astropy."""
    c = SkyCoord(ra=ra_deg * _u.degree, dec=dec_deg * _u.degree, frame="icrs")
    g = c.galactic
    return g.l.deg % 360.0, g.b.deg


def find_glon_offset(glon_values):
    """
    Given a list of GLON values (0-359, possibly with decimals), find the
    offset to apply to each so that the values are monotonically
    increasing across the panorama.

    Finds the largest gap between consecutive values around the circle; the
    panel after that gap is the start of the panorama, and any panel whose
    GLON is less than the start value gets +360 added.

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

    gaps = []
    n = len(unique)
    for i in range(n):
        gap = (unique[(i + 1) % n] - unique[i]) % 360
        gaps.append((gap, i))

    largest_gap_idx = max(gaps, key=lambda x: x[0])[1]
    start_val = unique[(largest_gap_idx + 1) % n]

    result = {}
    for v in unique:
        if v < start_val:
            result[v] = v + 360
        else:
            result[v] = v
    return result


def make_glat_glon_prefix(glat_snapped, glon_adjusted, decimals=RENAME_DECIMALS):
    """
    Build the GLAT/GLON filename prefix from already-snapped/rounded
    values, e.g. decimals=0, glat_snapped=-7, glon_adjusted=368 ->
    "GLAT007S_GLON368_".

    When decimals > 0, the decimal places are encoded directly into the
    filename too, e.g. decimals=1, glat_snapped=-7.2, glon_adjusted=368.5
    -> "GLAT007.2S_GLON368.5_". This matters: two panels correctly kept
    apart by round_coord() at, say, 0.7 degrees of separation could still
    collapse onto the very same integer-only label here and get wrongly
    merged into one group -- which is exactly what happens with a small
    (sub-1-degree) sensor FOV and dithered row/column spacing close to
    that FOV, e.g. a long-focal-length setup on a small sensor.

    Every prefix this produces is a fixed width for a given `decimals`
    (zero-padded), which extract_panel_prefix()'s regex relies on to find
    the label reliably regardless of what RENAME_DECIMALS is set to.
    """
    ns = "S" if glat_snapped < 0 else "N"
    if decimals > 0:
        width = 3 + 1 + decimals   # 3 integer digits + '.' + decimal digits
        glat_str = "{:0{w}.{d}f}".format(abs(glat_snapped), w=width, d=decimals)
        glon_str = "{:0{w}.{d}f}".format(glon_adjusted, w=width, d=decimals)
    else:
        glat_str = "{:03d}".format(int(round(abs(glat_snapped))))
        glon_str = "{:03d}".format(int(round(glon_adjusted)))
    return "GLAT{}{}_GLON{}_".format(glat_str, ns, glon_str)


# Matches a GLAT/GLON panel label at the start of a filename, decimals and
# all, e.g. "GLAT007N_GLON344_..." or "GLAT007.2S_GLON344.5_...". Used by
# extract_panel_prefix() below instead of a fixed character count (see the
# RENAME_DECIMALS config comment for why a fixed count breaks once decimals
# are involved). Galactic_2_Composite.py has its own copy of this same
# regex/function for matching this script's _stack output filenames -- keep
# them in sync if this pattern ever changes.
_PANEL_PREFIX_RE = re.compile(r'^(GLAT\d+(?:\.\d+)?[NS]_GLON\d+(?:\.\d+)?)_')


def extract_panel_prefix(filename):
    """
    Extract the panel-group key from a filename: the UNSOLVED_PREFIX label
    for unsolved files, or the GLAT/GLON label (with however many decimals
    RENAME_DECIMALS produced) for solved ones. Returns None if filename
    matches neither -- the caller should treat that as "leave ungrouped".
    """
    if filename.startswith(UNSOLVED_PREFIX):
        return UNSOLVED_PREFIX.rstrip("_")
    m = _PANEL_PREFIX_RE.match(filename)
    return m.group(1) if m else None


def _rename_with_retry(siril, fits_path, new_path):
    """
    Rename fits_path to new_path, retrying up to 5 times -- Windows
    releases Siril's file lock asynchronously after close/cd, so a short
    wait may be needed. Returns True on success.
    """
    import time as _time
    for attempt in range(5):
        try:
            if new_path.exists():
                new_path.unlink()
            fits_path.rename(new_path)
            return True
        except OSError as exc:
            if attempt < 4:
                _time.sleep(0.5)
            else:
                siril_log(siril, "  ERROR renaming " + fits_path.name + ": " + str(exc))
                return False
    return False


def rename_with_glat_glon(siril, process_dir):
    """
    Read each pp_light*.fits in process_dir and rename with GLAT/GLON prefix.

    Each file's GLAT/GLON is rounded (RENAME_DECIMALS) before wrap-around
    correction and panel labelling. GLON values are then wrap-corrected so
    files sort monotonically across the panorama (e.g. 351->351, 0->360,
    8->368 when the gap is at ~180 deg), and MERGE_LABELS is applied for
    any explicit manual overrides.

    Files with no readable RA/Dec (e.g. individual subs too short/noisy for
    ASTAP to solve) are, if RUN_GROUP_UNSOLVED, all renamed with the same
    fixed UNSOLVED_PREFIX instead -- grouping them into one stack per
    channel rather than each becoming its own single-frame group (since an
    unrenamed "pp_light_NNNNN.fits" has a different prefix for every N).
    If RUN_GROUP_UNSOLVED is False, they're left unrenamed and skipped, as
    before.

    Returns (renamed_count, skipped_count, error_count).
    """
    renamed = skipped = errors = 0
    pp_files = sorted(p for p in process_dir.iterdir()
                      if p.is_file()
                      and p.suffix.lower() in FITS_EXTENSIONS
                      and p.stem.startswith("pp_")
                      and not p.stem[:4].upper() == "GLAT")

    if not pp_files:
        return 0, 0, 0

    # Pass 1: read all coordinates, round, compute wrap-around offset.
    # Files with no RA/Dec go into unsolved_files instead.
    file_coords = {}   # path -> (glat_rounded, glon_rounded)
    unsolved_files = []
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
            unsolved_files.append(fits_path)
            continue
        ra_deg, dec_deg = coords
        l, b = radec_to_galactic(ra_deg, dec_deg)
        glon_rounded = round_coord(l, RENAME_DECIMALS) % 360
        glat_rounded = round_coord(b, RENAME_DECIMALS)
        file_coords[fits_path] = (glat_rounded, glon_rounded)
        glon_values.append(glon_rounded)

    # Compute wrap-corrected GLON mapping
    glon_offset_map = find_glon_offset(glon_values)
    if any(v != k for k, v in glon_offset_map.items()):
        adjusted = {k: v for k, v in glon_offset_map.items() if v != k}
        siril_log(siril, "  Wrap-around detected -- adjusting GLON values: "
                  + ", ".join(str(k) + "->" + str(v) for k, v in sorted(adjusted.items())))

    # Pass 2: rename with corrected GLON, then apply any manual merge override
    merged_count = 0
    for fits_path, (glat_rounded, glon_rounded) in file_coords.items():
        glon_adjusted = glon_offset_map.get(glon_rounded, glon_rounded)
        prefix = make_glat_glon_prefix(glat_rounded, glon_adjusted)
        if prefix in MERGE_LABELS:
            merged_count += 1
            prefix = MERGE_LABELS[prefix]
        new_path = fits_path.with_name(prefix + fits_path.name)
        if _rename_with_retry(siril, fits_path, new_path):
            renamed += 1
        else:
            errors += 1

    if merged_count:
        siril_log(siril, "  Manual merge override applied to " + str(merged_count) + " file(s).")

    # Pass 3: unsolved files -- group into one stack, or skip, per config
    if unsolved_files:
        if RUN_GROUP_UNSOLVED:
            siril_log(siril, "  " + str(len(unsolved_files))
                      + " file(s) with no RA/Dec -- grouping into one "
                      + UNSOLVED_PREFIX.strip('_') + " stack.")
            for fits_path in unsolved_files:
                new_path = fits_path.with_name(UNSOLVED_PREFIX + fits_path.name)
                if _rename_with_retry(siril, fits_path, new_path):
                    renamed += 1
                else:
                    errors += 1
        else:
            for fits_path in unsolved_files:
                siril_log(siril, "  SKIP (no RA/Dec): " + fits_path.name)
            skipped += len(unsolved_files)

    return renamed, skipped, errors


# Suffixes that identify output files produced by this script.
# Any FITS file whose stem ends with one of these (optionally followed by
# an exposure postfix, e.g. "_stack_300s") is skipped on re-runs so that
# previous stacks are never mixed back into the input data.
OUTPUT_SUFFIXES = ("_stack",)

# Prefixes that identify intermediate files from Galactic_0_Calibration.py.
# light_NNNNN.fits files are created by `convert` in the process/ directory
# (calibration output). They live in channel/process/ not channel/stacked/.
# and should never be picked up as input frames for stacking.
INTERMEDIATE_PREFIXES = ("light_", "flat_", "dark_", "bias_",
                         "pp_flat_", "pp_dark_", "pp_bias_")


def _strip_exposure_postfix(stem):
    """
    If stem ends with an exposure postfix (e.g. "..._300s"), return
    (stem_without_it, seconds). Otherwise return (stem, None).
    """
    m = re.search(r'^(.*)_(\d+)s$', stem)
    if m:
        return m.group(1), int(m.group(2))
    return stem, None


def is_output_file(path):
    """Return True if *path* looks like a file this script already produced
    or an intermediate calibration file that should be excluded."""
    stem = path.stem
    stem_no_exp, _ = _strip_exposure_postfix(stem)
    # Skip our own stack output files (with or without an exposure postfix)
    for suffix in OUTPUT_SUFFIXES:
        if stem.endswith(suffix) or stem_no_exp.endswith(suffix):
            return True
    # Skip intermediate convert/calibrate files from Galactic_0_Calibration
    for prefix in INTERMEDIATE_PREFIXES:
        if stem.startswith(prefix):
            return True
    return False


def read_exposure_seconds(fits_path):
    """
    Read this file's own exposure time from its FITS header, trying each
    key in EXPOSURE_KEYS in order. Returns float seconds, or None if no
    recognised keyword is present/readable.
    """
    try:
        from astropy.io import fits as _afits
        header = _afits.getheader(str(fits_path))
        for key in EXPOSURE_KEYS:
            if key in header:
                try:
                    return float(header[key])
                except (ValueError, TypeError):
                    continue
    except Exception:
        pass
    return None


def compute_total_exposure(files):
    """
    Sum each file's own exposure time (not count x nominal value, so this
    stays correct even with mixed exposure times within a group). Returns
    (total_seconds, any_missing) -- any_missing is True if at least one
    file had no readable exposure header, in which case the total is a
    partial/undercount and the caller should treat the postfix as unknown
    rather than reporting a misleadingly-precise wrong number.
    """
    total = 0.0
    any_missing = False
    for f in files:
        secs = read_exposure_seconds(f)
        if secs is None:
            any_missing = True
        else:
            total += secs
    return total, any_missing


def exposure_postfix(total_seconds, any_missing):
    """
    Format an exposure postfix like "_300s", or "" if the total is unknown
    (any input file was missing a readable exposure header) or zero --
    omitting the postfix is safer than showing a confidently-wrong number.
    """
    if any_missing or total_seconds <= 0 or not RUN_EXPOSURE_POSTFIX:
        return ""
    return "_{}s".format(int(round(total_seconds)))


def group_fits_by_channel(home_dir):
    """
    Scan each channel's process/ subdirectory for FITS input files and group
    them by their GLAT/GLON (or UNSOLVED) panel label -- see
    extract_panel_prefix(). Any file that doesn't match either pattern
    (e.g. Step 0 somehow left it unrenamed) is put in "_ungrouped_" and
    excluded from the result below, same as before.

    The stacked/ output directory is created if it doesn't exist.

    Returns dict { prefix: { channel_name: { "files": [Path], "work_dir": Path } } }
    where channel_name is e.g. "L".

    Files that look like previous stack outputs are excluded.
    """
    # channel_name -> { prefix -> [Path] }
    per_channel = {}
    for rel_dir in CHANNEL_DIRS:
        channel = rel_dir.split("/")[0]          # e.g. "L"
        scan_dir = home_dir / channel / "process" # always scan process/
        stacked_dir = home_dir / rel_dir          # output goes to stacked/

        if not scan_dir.is_dir():
            continue

        # Create stacked/ output dir if it doesn't exist
        stacked_dir.mkdir(parents=True, exist_ok=True)

        groups = defaultdict(list)
        for p in sorted(scan_dir.iterdir()):
            if not p.is_file():
                continue
            if p.suffix.lower() not in FITS_EXTENSIONS:
                continue
            if is_output_file(p):
                continue
            prefix = extract_panel_prefix(p.name) or "_ungrouped_"
            groups[prefix].append(p)
        if groups:
            per_channel[channel] = {"groups": dict(groups), "work_dir": stacked_dir}

    # Collect all prefixes that appear in at least one channel
    all_prefixes = set()
    for ch_data in per_channel.values():
        all_prefixes.update(ch_data["groups"].keys())
    all_prefixes.discard("_ungrouped_")

    # Build result: prefix -> { channel: { files, work_dir } }
    result = {}
    for prefix in sorted(all_prefixes):
        channel_files = {}
        for channel, ch_data in per_channel.items():
            if prefix in ch_data["groups"]:
                channel_files[channel] = {
                    "files":    ch_data["groups"][prefix],
                    "work_dir": ch_data["work_dir"],
                }
        if channel_files:
            result[prefix] = channel_files
    return result


def cleanup_group_dir(siril, group_dir, work_dir):
    """Remove the temporary _grp_ working directory."""
    import shutil as _sh
    # cd back to work_dir first so Siril does not hold a handle on group_dir
    cmd_safe(siril, "cd", str(work_dir))
    try:
        if group_dir.exists():
            _sh.rmtree(group_dir, ignore_errors=True)
            siril_log(siril, "  Cleaned up: " + group_dir.name)
    except Exception as exc:
        siril_log(siril, "  [WARNING] Could not remove " + str(group_dir) + ": " + str(exc))


def process_group(siril, group_prefix, files, work_dir, stack_out):
    """
    Run the full register -> stack -> denoise pipeline for one prefix group.
    stack_out is the exact output basename (already includes any exposure
    postfix) computed once by the caller, so it stays consistent between
    the skip-check, the actual save, and main()'s own pre-loop skip-check
    -- all three need to agree on the exact filename or resume/skip logic
    breaks.
    Returns True on success, False if a critical step failed.
    """
    n = len(files)
    siril_log(siril, "")
    siril_log(siril, "=" * 60)
    siril_log(siril, "Group: " + group_prefix + "  (" + str(n) + " file(s))")
    siril_log(siril, "=" * 60)

    # "." is allowed through unsanitized (not just alnum/"_") so a
    # decimal GLAT/GLON label (RENAME_DECIMALS > 0) survives into the
    # output filename exactly as extract_panel_prefix() expects it --
    # Galactic_2_Composite.py matches on this same "GLATnnn.nS_GLONnnn.n"
    # pattern when reading _stack.fits files back in.
    safe_prefix = "".join(c if (c.isalnum() or c in "_.") else "_" for c in group_prefix)

    def _remove_stale_legacy_output(legacy_prefix, final_path):
        """
        Remove any file matching "<legacy_prefix>_stack*" that isn't the
        current final_path -- cleans up leftovers from an older naming
        convention still sitting in the output directory.
        """
        target = legacy_prefix + "_stack"
        try:
            for candidate in work_dir.glob(target + "*"):
                if candidate.is_file() and candidate.resolve() != final_path.resolve():
                    try:
                        candidate.unlink()
                        siril_log(siril, "  Removed stale leftover from an older naming: "
                                  + candidate.name)
                    except OSError as exc:
                        siril_log(siril, "  [WARNING] Could not remove stale leftover "
                                  + candidate.name + ": " + str(exc))
        except OSError:
            pass

    if n < 2:
        # Single frame -- skip stacking/registration but copy it through
        # so downstream scripts (Galactic_2_Composite) can find it.
        siril_log(siril, "  Single frame -- copying as _stack (no stacking possible).")
        # Check skip first
        for ext in (".fits", ".fit", ".fts"):
            existing = work_dir / (stack_out + ext)
            if existing.exists():
                siril_log(siril, "  SKIP: output already exists: " + existing.name)
                return True
        src_file = files[0]
        dest_file = work_dir / (stack_out + src_file.suffix)
        try:
            import shutil as _shutil
            _shutil.copy2(src_file, dest_file)
            siril_log(siril, "  Copied: " + src_file.name + " -> " + dest_file.name)
            _remove_stale_legacy_output(safe_prefix, dest_file)
            return True
        except Exception as exc:
            siril_log(siril, "  [ERROR] Could not copy single frame: " + str(exc))
            return False

    # ------------------------------------------------------------------
    # Build names. Each group gets its own clean temp directory so
    # leftover files from a previous run can never bleed into this one.
    # ------------------------------------------------------------------
    group_dir    = work_dir / ("_grp_" + safe_prefix)

    seq_name      = safe_prefix
    reg_seq_name  = "r_" + safe_prefix
    # stack_out passed in by caller (already includes exposure postfix, if any)

    # Skip if the denoised output already exists (any extension).
    # Check BEFORE creating the group_dir so no empty directory is left.
    for ext in (".fits", ".fit", ".fts"):
        existing = work_dir / (stack_out + ext)
        if existing.exists():
            siril_log(siril, "  SKIP: output already exists: " + existing.name)
            return True

    # Always start with a completely empty directory to prevent stale
    # files from a prior run inflating the file count.
    if group_dir.exists():
        import shutil as _shutil
        _shutil.rmtree(group_dir, ignore_errors=True)
    group_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: Populate the group sub-directory and convert to sequence.
    # We also tell Siril which extension to use (setext) so that convert
    # and register agree on the filename suffix -- without this, convert
    # may write .fit while register looks for .fits (or vice-versa).
    # ------------------------------------------------------------------
    siril_log(siril, "  [1/6] Converting " + str(n) + " files into sequence '" + seq_name + "'...")

    if not cmd_safe(siril, "cd", str(group_dir)):
        return False

    # Match Siril's working extension to whatever the source files use,
    # so that convert and register see the same suffix.
    src_ext = files[0].suffix.lstrip(".")   # e.g. "fits" or "fit"
    cmd_safe(siril, "setext", src_ext)

    # Copy each source file into the group dir.
    # Symlinks are tried first (instant, no disk space); Windows without
    # developer mode does not allow symlinks so we fall back to a copy.
    import shutil as _shutil
    for src_file in files:
        dst = group_dir / src_file.name
        try:
            dst.symlink_to(src_file)
        except (OSError, NotImplementedError):
            _shutil.copy2(src_file, dst)

    if not cmd_safe(siril, "convert", seq_name, "-out=./"):
        siril_log(siril, "  [ERROR] convert failed -- skipping group.")
        return False

    # ------------------------------------------------------------------
    # Step 2: Register
    #
    # STACK_FRAMING="min" uses Siril's documented two-step approach for
    # cropping to the common overlap area (removes ragged/partial-coverage
    # borders left by dithering between subs):
    #   register seq -2pass          (compute transforms only, no output yet)
    #   seqapplyreg seq -framing=min (apply transforms + crop to overlap,
    #                                 writes the r_ prefixed output files)
    # STACK_FRAMING="current" keeps the old single-pass register, which
    # writes the r_ files directly with no cropping.
    # ------------------------------------------------------------------
    siril_log(siril, "  [2/6] Registering (-transf=" + REGISTER_TRANSF
              + ", framing=" + STACK_FRAMING + ")...")
    # Set the last frame as reference (the first can be wobbly from mount
    # settling after a slew). NOTE: -2pass runs its own quality-based
    # reference selection, which may override this setref -- Siril's docs
    # don't specify which takes precedence, but -2pass's choice should be
    # at least as good.
    cmd_safe(siril, "setref", seq_name, str(n))

    if STACK_FRAMING == "min":
        if not cmd_safe(siril, "register", seq_name, "-2pass", "-transf=" + REGISTER_TRANSF):
            siril_log(siril, "  [ERROR] registration (2-pass) failed -- skipping group.")
            return False
        if not cmd_safe(siril, "seqapplyreg", seq_name, "-framing=min"):
            # Long/undithered sessions can accumulate enough drift that no
            # single region is shared by every frame at once -- Siril's
            # own error is "intersection of all images is null or
            # negative". The transforms from the -2pass above are still
            # valid, so fall back to applying them without cropping
            # (framing=current) rather than losing the whole group.
            siril_log(siril, "  [WARNING] seqapplyreg -framing=min found no common"
                      + " overlap across all frames (likely a long/undithered"
                      + " session) -- falling back to no cropping.")
            if not cmd_safe(siril, "seqapplyreg", seq_name, "-framing=current"):
                siril_log(siril, "  [ERROR] seqapplyreg fallback also failed -- skipping group.")
                return False
    else:
        if not cmd_safe(siril, "register", seq_name, "-transf=" + REGISTER_TRANSF):
            siril_log(siril, "  [ERROR] registration failed -- skipping group.")
            return False

    # ------------------------------------------------------------------
    # Step 3: Stack
    # Force 32-bit float output BEFORE stacking.
    # When input files are 16-bit camera FITS, Siril automatically outputs
    # 16-bit stacks. With addscale normalisation, bright star cores in
    # 16-bit stacks are clipped at 65535 -- information is lost and the
    # clipped pixels cause colour problems in LRGB composition.
    # 32-bit float stores the true normalised value (e.g. 0.94) with no
    # clipping, preserving all colour information through the pipeline.
    # set32bits persists until set16bits is called or Siril restarts.
    # ------------------------------------------------------------------
    cmd_safe(siril, "set32bits")
    siril_log(siril, "  Output set to 32-bit float for stacking.")

    MIN_FRAMES_FOR_REJECTION = 5
    if n < MIN_FRAMES_FOR_REJECTION:
        stack_type_used = "med"   # median -- inherent single-outlier rejection
        siril_log(siril, "  [3/6] Stacking " + str(n) + " frames -> median"
                  + " (too few for sigma rejection) -> " + stack_out + " ...")
        if not cmd_safe(
            siril,
            "stack", reg_seq_name,
            stack_type_used,
            "-norm=" + STACK_NORM,
            "-output_norm",
            "-out=" + stack_out,
        ):
            siril_log(siril, "  [ERROR] stacking failed -- skipping denoise.")
            return False
    else:
        stack_type_used = STACK_TYPE
        siril_log(siril, "  [3/6] Stacking " + str(n) + " frames -> "
                  + STACK_TYPE + " rejection -> " + stack_out + " ...")
        if not cmd_safe(
            siril,
            "stack", reg_seq_name,
            STACK_TYPE,
            str(STACK_SIGMA_LOW),
            str(STACK_SIGMA_HIGH),
            "-norm=" + STACK_NORM,
            "-output_norm",
            "-out=" + stack_out,
        ):
            siril_log(siril, "  [ERROR] stacking failed -- skipping denoise.")
            return False

    # ------------------------------------------------------------------
    # Step 4/5/6: BlurXTerminator deconvolution, then NoiseXTerminator,
    # then GraXpert Denoise
    # BGE is done after LRGB recomposition in Galactic_3_Stretch.py --
    # per-channel BGE before recomposition causes colour casts at panel
    # edges because each channel gets a different background model.
    # Running BGE on the combined LRGB image uses one consistent model
    # across all channels simultaneously.
    # ------------------------------------------------------------------

    # Find the stacked file (Siril writes .fit or .fits depending on setext)
    stack_path = None
    for ext in (".fit", ".fits", ".fts"):
        candidate = group_dir / (stack_out + ext)
        if candidate.exists():
            stack_path = candidate
            break

    if stack_path is None:
        siril_log(siril, "  [ERROR] Stacked file not found -- skipping post-processing.")
        cleanup_group_dir(siril, group_dir, work_dir)
        return False

    # Load the stack
    if not cmd_safe(siril, "load", str(stack_path)):
        siril_log(siril, "  [ERROR] Could not load stacked file.")
        cleanup_group_dir(siril, group_dir, work_dir)
        return False

    # BlurXTerminator deconvolution (optional -- see RUN_BLURXTERMINATOR
    # config). Runs on the linear stack, before denoise, since
    # deconvolution wants the cleanest data available and GraXpert
    # afterwards cleans up any noise it amplifies.
    bxt_ok = False
    if RUN_BLURXTERMINATOR:
        if BXT_CORRECT_ONLY:
            siril_log(siril, "  [4/6] BlurXTerminator: optical-aberration correction only...")
            bxt_ok = cmd_safe(
                siril,
                "pyscript", "BlurXTerminator.py",
                "--correct-only",
            )
        else:
            siril_log(siril, "  [4/6] BlurXTerminator (--ss=" + str(BXT_SHARPEN_STARS)
                      + " --sn=" + str(BXT_SHARPEN_NONSTELLAR)
                      + " --ash=" + str(BXT_ADJUST_STAR_HALOS)
                      + ", auto_psf=" + str(BXT_AUTOMATIC_PSF) + ")...")
            bxt_args = [
                "--ss", str(BXT_SHARPEN_STARS),
                "--ash", str(BXT_ADJUST_STAR_HALOS),
                "--sn", str(BXT_SHARPEN_NONSTELLAR),
            ]
            if BXT_AUTOMATIC_PSF:
                bxt_args.append("--ansp")
            else:
                bxt_args += ["--no-ansp", "--nsd", str(BXT_NONSTELLAR_RADIUS)]
            bxt_ok = cmd_safe(siril, "pyscript", "BlurXTerminator.py", *bxt_args)
        if not bxt_ok:
            siril_log(siril, "  [WARNING] BlurXTerminator failed -- continuing without it.")
    else:
        siril_log(siril, "  [4/6] BlurXTerminator skipped (RUN_BLURXTERMINATOR = False).")

    # RC-Astro NoiseXTerminator (optional -- see RUN_NOISEXTERMINATOR
    # config). Runs after BlurXTerminator and before GraXpert denoise --
    # both denoise tools are independent switches, so either, both, or
    # neither can run; running both is usually redundant.
    nxt_ok = False
    if RUN_NOISEXTERMINATOR:
        siril_log(siril, "  [5/6] RC-Astro NoiseXTerminator (--dn=" + str(NXT_DENOISE)
                  + " --it=" + str(NXT_ITERATIONS) + ")...")
        nxt_args = ["--dn", str(NXT_DENOISE), "--it", str(NXT_ITERATIONS)]
        nxt_ok = cmd_safe(siril, "pyscript", "NoiseXTerminator.py", *nxt_args)
        if not nxt_ok:
            siril_log(siril, "  [WARNING] NoiseXTerminator failed -- continuing without it.")
    else:
        siril_log(siril, "  [5/6] NoiseXTerminator skipped (RUN_NOISEXTERMINATOR = False).")

    # Denoise (optional -- see RUN_DENOISE config)
    denoise_ok = False
    if RUN_DENOISE:
        siril_log(siril, "  [6/6] Denoising via GraXpert-AI.py -denoise (strength=" + str(DENOISE_STRENGTH) + ")...")
        denoise_ok = cmd_safe(
            siril,
            "pyscript", "GraXpert-AI.py",
            "-denoise",
            "-strength=" + str(DENOISE_STRENGTH),
        )
    else:
        siril_log(siril, "  [6/6] Denoising skipped (RUN_DENOISE = False).")

    # Optional: Aberration Removal (GUI dialog -- see RUN_ABERRATION_REMOVER config)
    ab_ok = False
    if RUN_ABERRATION_REMOVER:
        siril_log(siril, "  Aberration removal (dialog will open for "
                  + group_prefix + ")...")
        ab_ok = cmd_safe(siril, "pyscript", "AberrationRemover.py")
        if not ab_ok:
            siril_log(siril, "  [WARNING] AberrationRemover failed -- continuing.")

    # Save result -- named _stack regardless of which steps succeeded
    # so Galactic_2_Composite can find it by its expected filename
    final_path = work_dir / (stack_out + ".fits")
    if not cmd_safe(siril, "save", str(final_path)):
        siril_log(siril, "  [ERROR] Could not save result to " + str(final_path))
        cleanup_group_dir(siril, group_dir, work_dir)
        return False

    steps_done = ["stacked"]
    if bxt_ok:     steps_done.append("BlurXTerminator")
    if nxt_ok:     steps_done.append("NoiseXTerminator")
    if denoise_ok: steps_done.append("denoised")
    if ab_ok:      steps_done.append("aberration corrected")
    siril_log(siril, "  OK  Saved (" + " + ".join(steps_done) + "): " + final_path.name)

    _remove_stale_legacy_output(safe_prefix, final_path)

    # Clean up the temporary group directory
    cleanup_group_dir(siril, group_dir, work_dir)
    return True


def main():
    siril = s.SirilInterface()

    try:
        siril.connect()
        siril_log(siril, "GalacticStack-AI v1.3.0 connected.")
    except Exception as exc:
        # connect() failed -- siril.log() won't work, so print only
        print("GalacticStack-AI: could not connect to Siril: " + str(exc))
        return

    try:
        siril.cmd("requires", "1.4.0")
    except Exception:
        siril.error_messagebox(
            "GalacticStack-AI requires Siril 1.4.0 or later. Please update Siril."
        )
        siril.disconnect()
        return

    try:
        home_dir = Path(siril.get_siril_wd())
        siril_log(siril, "Home directory: " + str(home_dir))

        # ------------------------------------------------------------------
        # Step 0: Rename each channel's calibrated lights with a GLAT/GLON
        # panel prefix, before grouping. See the config comment above
        # RENAME_DECIMALS for why this lives here rather than in
        # Galactic_0_Calibration.py.
        # ------------------------------------------------------------------
        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "Step 0: Renaming panels with GLAT/GLON prefix...")
        siril_log(siril, "=" * 60)
        total_renamed = total_skipped = total_errors = 0
        for rel_dir in CHANNEL_DIRS:
            channel = rel_dir.split("/")[0]
            process_dir = home_dir / channel / "process"
            if not process_dir.is_dir():
                continue
            renamed, skipped, errors = rename_with_glat_glon(siril, process_dir)
            if renamed or skipped or errors:
                siril_log(siril, "  " + channel + ": renamed " + str(renamed)
                          + "  skipped (no RA/Dec) " + str(skipped)
                          + "  errors " + str(errors))
            total_renamed += renamed
            total_skipped += skipped
            total_errors += errors
        if total_skipped:
            siril_log(siril, "  " + str(total_skipped) + " file(s) had no RA/Dec and were left"
                      + " unrenamed -- plate-solve them (e.g. with ASTAP) and re-run to include them.")

        channels_scanned = [rel_dir.split("/")[0] + "/process" for rel_dir in CHANNEL_DIRS]
        siril_log(siril, "Scanning: " + ", ".join(channels_scanned))
        siril_log(siril, "Output to: " + ", ".join(CHANNEL_DIRS))

        channel_groups = group_fits_by_channel(home_dir)

        if not channel_groups:
            siril_log(siril, "No FITS files found in any channel process/ subdirectory.")
            siril_log(siril, "Expected input files in: " + ", ".join(channels_scanned))
            siril.disconnect()
            return

        # Report what was found
        siril_log(siril, "Found " + str(len(channel_groups)) + " prefix group(s):")
        for prefix, chan_data in channel_groups.items():
            total = sum(len(v["files"]) for v in chan_data.values())
            channels = ", ".join(ch + ":" + str(len(v["files"]))
                                 for ch, v in chan_data.items())
            siril_log(siril, "  " + prefix + "  ->  " + channels
                      + "  (" + str(total) + " total)")

        ok = fail = skip = 0
        results = []   # (channel, prefix, n_files, status)
        for prefix, chan_data in channel_groups.items():
            for channel, ch_info in chan_data.items():
                files    = ch_info["files"]
                work_dir = ch_info["work_dir"]
                siril_log(siril, " ")
                siril_log(siril, "Channel " + channel + " / " + prefix
                          + " (" + str(len(files)) + " file(s))")
                # Exposure postfix has to be computed BEFORE the skip-check
                # (not after), since the expected filename depends on it --
                # otherwise the skip-check would look for the wrong name
                # and never find an already-completed group.
                # See the matching comment in process_group() -- "." must
                # survive unsanitized here too, for the same reason.
                safe_prefix = "".join(c if (c.isalnum() or c in "_.") else "_"
                                     for c in prefix)
                total_exp, exp_missing = compute_total_exposure(files)
                exp_suffix = exposure_postfix(total_exp, exp_missing)
                # Channel name included so files for different channels of
                # the same panel are never identically named.
                stack_out = safe_prefix + "_" + channel + "_stack" + exp_suffix

                already_done = any((work_dir / (stack_out + ext)).exists()
                                   for ext in (".fits", ".fit", ".fts"))
                if already_done:
                    skip += 1
                    results.append((channel, prefix, len(files), "SKIP"))
                elif process_group(siril, prefix, files, work_dir, stack_out):
                    ok += 1
                    results.append((channel, prefix, len(files), "OK"))
                else:
                    fail += 1
                    results.append((channel, prefix, len(files), "FAIL"))

        # Restore working directory to home when done
        cmd_safe(siril, "cd", str(home_dir))

        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "Galactic_1_Stack complete.")
        siril_log(siril, "=" * 60)
        siril_log(siril, "  {:<4} {:<18} {:>6} {:>6}".format(
                  "Ch", "Panel", "Frames", "Result"))
        siril_log(siril, "  " + "-" * 38)
        for channel, prefix, n_files, status in results:
            siril_log(siril, "  {:<4} {:<18} {:>6} {:>6}".format(
                      channel, prefix, n_files, status))
        siril_log(siril, " ")
        siril_log(siril, "  OK  : " + str(ok)
                  + "   SKIP: " + str(skip)
                  + "   FAIL: " + str(fail)
                  + "   TOTAL: " + str(ok + skip + fail))
        siril_log(siril, "  Next: run Galactic_2_Composite.py")
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


# ---------------------------------------------------------------------------
# Siril executes scripts via exec(), so __name__ is NOT '__main__'.
# Call main() unconditionally at module level so it always runs.
# ---------------------------------------------------------------------------
main()