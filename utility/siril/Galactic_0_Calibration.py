# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_0_Calibration.py
# Version: 1.1.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# ==============================================================================
# OVERVIEW
# ==============================================================================
# Calibrates and preprocesses light frames for every filter found under the
# Siril home directory. Output is ready for Galactic_1_Stack.py, which
# renames each calibrated light with a GLAT/GLON panel label (derived from
# its own RA/Dec header) and groups panels as its first step.
#
# Lights/darks/biases/flats can be FITS or camera RAW (e.g. Canon CR3) --
# see RAW_EXTENSIONS. Siril's own convert step does the conversion; OSC RAW
# frames are also debayered as part of calibration (see preprocess_filter).
#
# Steps, in order:
#   0. Normalise capture-software directory names       (optional, RUN_NINA_DIR_NORMALIZE)
#   1. Scan and report available calibration/light data
#   2. Build master bias and master dark (shared across all filters)
#   3. Build master flat (per filter)
#   4. Calibrate lights -> <filter>/process/pp_light_NNNNN.fits
#
# GLAT/GLON renaming happens in Galactic_1_Stack.py instead of here, so you
# can plate-solve the calibrated FITS files in between if your capture
# software didn't record RA/Dec (e.g. a camera RAW format like CR3 has
# nowhere to store a plate-solve solution, but the calibrated FITS output
# does).
#
# ==============================================================================
# DIRECTORY STRUCTURE
# ==============================================================================
#   <home>/
#     L/lights/              <- light frames (any filter may be absent)
#     R/lights/
#     G/lights/
#     B/lights/
#     Ha/lights/
#     Sii/lights/
#     Oiii/lights/
#     OSC/lights/            <- one-shot-colour camera (no filter wheel)
#     calibration/
#       X/
#         darks/             <- darks, shared across all filters (incl. OSC)
#         biases/            <- biases, shared across all filters (incl. OSC)
#       L/flats/              <- per-filter flats (optional)
#       R/flats/
#       G/flats/
#       B/flats/
#       Ha/flats/
#       Sii/flats/
#       Oiii/flats/
#       OSC/flats/
#
# If your capture software writes LIGHT/DARK/BIAS/FLAT folders instead --
# including an OSC layout with no filter subfolder at all -- Step 0
# reorganises them into the structure above automatically.

import sirilpy as s
import math
import os
import traceback
from pathlib import Path
from collections import defaultdict

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# ------------------------------------------------------------------------
# Directory layout (used throughout)
# ------------------------------------------------------------------------
FILTER_DIRS = ["L", "R", "G", "B", "Ha", "Sii", "Oiii", "OSC"]   # processing order

CALIB_DIR  = "calibration"
SHARED_DIR = "X"              # darks/ and biases/ live here, shared by all filters

LIGHTS_SUBDIR  = "lights"
FLATS_SUBDIR   = "flats"
DARKS_SUBDIR   = "darks"
BIASES_SUBDIR  = "biases"
PROCESS_SUBDIR = "process"

FITS_EXTENSIONS = {".fits", ".fit", ".fts"}

# Camera RAW formats Siril can convert directly (via convert, using its
# bundled libraw) -- lights/darks/biases/flats can be in any of these, or
# FITS, or a mix. Used only for counting/reporting what's available before
# conversion; Siril's own convert command does the actual work regardless
# of which of these are present.
RAW_EXTENSIONS = {".cr2", ".cr3", ".nef", ".arw", ".orf", ".raf",
                  ".rw2", ".pef", ".dng", ".srw", ".x3f"}

# ------------------------------------------------------------------------
# Step 0: Directory normalisation -- RUN_NINA_DIR_NORMALIZE
# ------------------------------------------------------------------------
# Renames capture-software LIGHT/DARK/BIAS/FLAT folders to
# lights/darks/biases/flats. An OSC layout (these folders sitting directly
# under <home>, with no filter subfolder) is moved into the OSC pseudo-filter
# structure above; any other match is renamed in place. Set False if your
# folders are already named correctly.
RUN_NINA_DIR_NORMALIZE = True

NINA_RENAME_MAP = {
    "LIGHT": LIGHTS_SUBDIR,
    "DARK":  DARKS_SUBDIR,
    "BIAS":  BIASES_SUBDIR,
    "FLAT":  FLATS_SUBDIR,
}
OSC_FILTER_NAME = "OSC"        # must match an entry in FILTER_DIRS above

# ------------------------------------------------------------------------
# Step 2: Master calibration frames
# ------------------------------------------------------------------------
MASTER_BIAS_NAME = "master_bias"      # written into calibration/X/
MASTER_DARK_NAME = "master_dark"      # written into calibration/X/ (bias-subtracted)
MASTER_FLAT_NAME = "master_flat"      # written into calibration/<filter>/
# ==============================================================================


# ---------------------------------------------------------------------------
# Helpers
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
    # Auto-quote any argument containing whitespace (e.g. Windows paths
    # with spaces) so Siril's command parser treats it as one token.
    args = tuple(_quote_if_needed(a) for a in args)
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


def count_images(directory):
    """
    Return number of FITS or camera RAW files in directory, or 0 if absent.
    Use this (not count_fits) for lights/darks/biases/flats directories
    before conversion -- they may contain RAW files (e.g. Canon CR3) that
    Siril's own convert step will handle, but count_fits alone would miss,
    making the directory look empty and skipping it entirely.
    """
    if not directory or not directory.is_dir():
        return 0
    exts = FITS_EXTENSIONS | RAW_EXTENSIONS
    return sum(1 for p in directory.iterdir()
               if p.is_file() and p.suffix.lower() in exts)


# ---------------------------------------------------------------------------
# NINA directory normalisation (see RUN_NINA_DIR_NORMALIZE config comment)
# ---------------------------------------------------------------------------

def _merge_or_move_dir(siril, src_dir, dst_dir):
    """
    Move src_dir's contents into dst_dir. If dst_dir doesn't exist yet,
    this is a fast, simple rename of the whole directory. If dst_dir
    already has content (e.g. a previous night's session already
    populated it), files are merged in one at a time instead -- any
    individual filename collision is left in place and skipped (with a
    warning) rather than silently overwritten, since calibration frames
    or lights from a different session might not actually be compatible
    even if the folder name matches.
    Returns the number of files moved.
    """
    if not dst_dir.exists():
        dst_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            src_dir.rename(dst_dir)
            n = sum(1 for p in dst_dir.iterdir() if p.is_file())
            siril_log(siril, "  Moved: " + str(src_dir) + "  ->  " + str(dst_dir)
                      + "  (" + str(n) + " file(s))")
            return n
        except OSError as exc:
            siril_log(siril, "  [WARNING] Could not move " + str(src_dir)
                      + " -> " + str(dst_dir) + ": " + str(exc))
            return 0

    # Destination already exists -- merge file by file.
    dst_dir.mkdir(parents=True, exist_ok=True)
    moved = skipped = 0
    for item in list(src_dir.iterdir()):
        target = dst_dir / item.name
        if target.exists():
            skipped += 1
            continue
        try:
            item.rename(target)
            moved += 1
        except OSError as exc:
            siril_log(siril, "  [WARNING] Could not move " + str(item) + ": " + str(exc))
    siril_log(siril, "  Merged into existing " + str(dst_dir) + ": "
              + str(moved) + " file(s) moved, " + str(skipped) + " skipped (already present)")
    try:
        next(src_dir.iterdir())
    except StopIteration:
        src_dir.rmdir()
    except OSError:
        pass
    return moved


def normalize_nina_directories(siril, home_dir):
    """
    Rename/reorganise NINA-style LIGHT/DARK/BIAS/FLAT folders into what
    this pipeline (and Siril generally) expects -- see the
    RUN_NINA_DIR_NORMALIZE config comment for the two passes this does.
    """
    calib_root = home_dir / CALIB_DIR
    shared_dir = calib_root / SHARED_DIR

    # ------------------------------------------------------------------
    # Pass 1: OSC layout -- LIGHT/DARK/BIAS/FLAT directly under home,
    # with no filter subfolder. Move + rename into the OSC pseudo-filter
    # structure so the rest of the pipeline treats OSC like any other
    # filter, with no special-casing needed anywhere else.
    # ------------------------------------------------------------------
    osc_targets = {
        "LIGHT": home_dir / OSC_FILTER_NAME / LIGHTS_SUBDIR,
        "FLAT":  calib_root / OSC_FILTER_NAME / FLATS_SUBDIR,
        "DARK":  shared_dir / DARKS_SUBDIR,
        "BIAS":  shared_dir / BIASES_SUBDIR,
    }
    any_osc = False
    handled_paths = set()
    for raw_name, dst_dir in osc_targets.items():
        src_dir = home_dir / raw_name
        if src_dir.is_dir():
            if not any_osc:
                siril_log(siril, "  Detected OSC-style layout (no filter subfolder) --"
                          + " reorganising into " + OSC_FILTER_NAME + "/ structure.")
                any_osc = True
            handled_paths.add(src_dir.resolve())
            _merge_or_move_dir(siril, src_dir, dst_dir)
            if src_dir.is_dir():
                siril_log(siril, "  [WARNING] " + str(src_dir)
                          + " still has unmerged file(s) left behind (name collisions"
                          + " with existing files at the destination) -- check it manually.")

    # ------------------------------------------------------------------
    # Pass 2: general case -- rename any OTHER directory literally named
    # LIGHT/DARK/BIAS/FLAT anywhere in the tree, in place (no moving).
    # This is the normal filter-wheel case, where NINA already nests
    # these under the right filter/shared folder, just with the wrong
    # name. topdown=False so renaming a directory doesn't disrupt os.walk
    # part-way through iterating its parent.
    # ------------------------------------------------------------------
    renamed = 0
    for current_path, dirnames, _filenames in os.walk(str(home_dir), topdown=False):
        for dirname in dirnames:
            if dirname not in NINA_RENAME_MAP:
                continue
            old_path = Path(current_path) / dirname
            if not old_path.is_dir():
                continue
            if old_path.resolve() in handled_paths:
                continue   # already dealt with (or deliberately left) by Pass 1
            new_path = Path(current_path) / NINA_RENAME_MAP[dirname]
            if new_path.exists():
                # Merge rather than skip -- consistent with the OSC pass,
                # and handles re-running this across multiple sessions.
                _merge_or_move_dir(siril, old_path, new_path)
            else:
                try:
                    old_path.rename(new_path)
                    siril_log(siril, "  Renamed: " + str(old_path) + "  ->  " + str(new_path))
                    renamed += 1
                except OSError as exc:
                    siril_log(siril, "  [WARNING] Could not rename " + str(old_path)
                              + ": " + str(exc))

    if not any_osc and renamed == 0:
        siril_log(siril, "  No NINA-style LIGHT/DARK/BIAS/FLAT directories found -- nothing to do.")


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
    #
    # For OSC (one-shot-colour) lights, the RAW/converted frames are still
    # Bayer-pattern mono data at this point -- -cfa tells calibrate to treat
    # them as such, -equalize_cfa equalises the 4 Bayer channels' mean level
    # in the flat before applying it (avoids a colour cast from the flat),
    # and -debayer demosaics into an RGB image as the last step. Without
    # these, OSC output would silently stay as flat, uncoloured Bayer data.
    pp_args = ["calibrate", "light"]
    if master_dark_path and master_dark_path.exists():
        pp_args.append("-dark=" + str(master_dark_path))
        pp_args.append("-cc=dark")   # hot pixel cosmetic correction from dark
    if master_flat_path and master_flat_path.exists():
        pp_args.append("-flat=" + str(master_flat_path))
    if filter_name == OSC_FILTER_NAME:
        pp_args.append("-cfa")
        pp_args.append("-equalize_cfa")
        pp_args.append("-debayer")
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
        siril_log(siril, "Galactic_0_Calibration v1.0.1 connected.")
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
        # Step 0: Normalise NINA-style directory names (LIGHT/DARK/BIAS/FLAT
        # -> lights/darks/biases/flats), including reorganising an OSC
        # (no filter subfolder) layout into the OSC pseudo-filter structure.
        # Must happen before any scanning below.
        # ------------------------------------------------------------------
        if RUN_NINA_DIR_NORMALIZE:
            siril_log(siril, " ")
            siril_log(siril, "=" * 60)
            siril_log(siril, "Normalising capture directory names...")
            siril_log(siril, "=" * 60)
            normalize_nina_directories(siril, home_dir)

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

        n_darks  = count_images(darks_dir)
        n_biases = count_images(biases_dir)

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
            n_lights = count_images(lights_dir)
            n_flats  = count_images(flats_dir)
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
        # Steps 3-4: Per-filter processing
        # ------------------------------------------------------------------
        ok_filters = []
        fail_filters = []

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
        siril_log(siril, "  {:<8} {:>8} {:>8} {:>10}".format(
                  "Filter", "Lights", "Flats", "Calibrated"))
        siril_log(siril, "  " + "-" * 38)
        for filt in ok_filters:
            info = filter_info[filt]
            n_cal = sum(1 for p in info["process_dir"].iterdir()
                        if p.is_file()
                        and p.suffix.lower() in {".fits", ".fit", ".fts"}
                        and p.stem.startswith("pp_"))
            siril_log(siril, "  {:<8} {:>8} {:>8} {:>10}".format(
                      filt, info["n_lights"], info["n_flats"], n_cal))
        for filt in fail_filters:
            siril_log(siril, "  {:<8}   FAILED".format(filt))
        siril_log(siril, " ")
        siril_log(siril, "  Filters OK    : " + (", ".join(ok_filters) if ok_filters else "none"))
        siril_log(siril, "  Filters failed: " + (", ".join(fail_filters) if fail_filters else "none"))
        siril_log(siril, "  Next: if your capture software didn't record RA/Dec (e.g. a"
                  + " camera RAW format with nowhere to store it), plate-solve the"
                  + " pp_light_*.fits files in each <filter>/process/ directory now"
                  + " (e.g. with ASTAP's bulk solve). Then run Galactic_1_Stack.py,"
                  + " which renames and groups panels as its first step.")
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