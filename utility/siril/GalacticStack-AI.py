# SPDX-License-Identifier: GPL-3.0-or-later
# GalacticStack-AI.py
# Version: 1.1.0
# Author:  Generated for alpaca-benro-polaris utility suite
# Contact: https://github.com/scriptable
#
# Galactic Panorama Siril Script
# ------------------------------
# Save time by automatically stacking and denoising groups of FITS files into each Galactic Pano Panel
# Can be used for OSC or monochrome images. Makes it easy to match the monochrome channels for each Panel by Galactic coordinates.
# 
# Installation
# -----------
#   1. Copy script into C:\Users\YourUserName\AppData\Roaming\siril\scripts, creating directory if it doenst exist
#   2. Using Siril > Scripts > Get Scripts, check the above folder is included, then click the refresh button
#   3. The Siril log should show 
#      17:35:28: Searching for scripts in: "C:\Users\YourUserName\AppData\Roaming\siril\scripts"...
#      17:35:28: Loading script: GalacticStack-AI.py
#
# File Preparation
# -----------
#   1. Use Siril to preprocess biases, darks, flats and lights 
#   2. Use ASTAP to cull and plate-solve all preprocessed FITS files 
#   3. Copy all plate-solved, preprocessed files eg. pp_light_*.fit into a working directory
#   4. Use the utility/fits_galactic.py to rename the files based on Galactic co-ordinates
#   5. Using Siril, set the Home directory to your working directory
#   6. Using Siril > Scripts > Python Scripts > Scripts > GalacticStack-AI; to run this script
# 
# Description
# -----------
# Groups all FITS files in the Siril working directory by the first 16
# characters of their filename (e.g. GLAT022N_GLON344 -> one group), then
# for every group:
#   1.  Converts the group's files into a Siril sequence
#   2.  Registers (aligns) the sequence with global star-matching
#   3.  Stacks with sigma-clipping rejection and average combination
#   4.  Loads the stacked image and applies GraXpert AI denoising
#   5.  Saves the denoised result as <prefix>_stack_denoised.fits
#
# Prerequisites
# -------------
#   Siril 1.4.0 or later with the built-in sirilpy module.
#   GraXpert-AI.py installed via Scripts -> Get Scripts.
#   GraXpert executable path set in Preferences -> Miscellaneous.
#   FITS files renamed with GLAT/GLON prefix by fits_add_galactic.py --rename
#   e.g.  GLAT019S_GLON209_Light_001.fits
#
# Usage
# -----
#   Set the Siril working directory to the folder containing your renamed
#   FITS files, then run from the Scripts menu.
#
# Configuration
# -------------
#   Edit the constants in the CONFIGURATION block below.

import sirilpy as s
import os
import traceback
from pathlib import Path
from collections import defaultdict

# ---------------------------------------------------------------------------
# CONFIGURATION -- edit these values as needed
# ---------------------------------------------------------------------------
DENOISE_STRENGTH = 1.0      # GraXpert denoising strength: 0.0 (none) to 1.0 (max)
REGISTER_TRANSF  = "homography" # registration transform: shift / similarity / affine / homography
STACK_TYPE       = "rej"    # stacking type (rej = sigma-clipping rejection)
STACK_SIGMA_LOW  = 3        # lower sigma threshold for rejection
STACK_SIGMA_HIGH = 3        # upper sigma threshold for rejection
STACK_NORM       = "addscale"  # normalisation: addscale / add / mul / no
FITS_EXTENSIONS  = {".fits", ".fit", ".fts"}
PREFIX_LENGTH    = 16       # number of filename characters used to group files
# ---------------------------------------------------------------------------


def siril_log(siril, msg):
    """Write a plain-ASCII message to the Siril log.
    siril.log() already echoes to the Siril console -- no print() needed.
    Empty strings crash the pipe protocol, so replace them with a space.
    """
    safe = msg.encode("ascii", errors="replace").decode("ascii")
    if not safe:
        safe = " "
    siril.log(safe)


def cmd_safe(siril, *args):
    """
    Run a Siril command, returning True on success, False on failure.
    Errors are logged but never re-raised, so the loop continues.
    """
    try:
        siril.cmd(*args)
        return True
    except Exception as exc:
        siril_log(siril, "  [WARNING] Command failed: " + " ".join(str(a) for a in args))
        siril_log(siril, "            " + str(exc))
        return False


# Suffixes that identify output files produced by this script.
# Any FITS file whose stem ends with one of these is skipped on re-runs
# so that previous stacks are never mixed back into the input data.
OUTPUT_SUFFIXES = ("_stack", "_stack_denoised")


def is_output_file(path):
    """Return True if *path* looks like a file this script already produced."""
    stem = path.stem  # filename without extension, e.g. "GLAT019S_GLON209_stack"
    for suffix in OUTPUT_SUFFIXES:
        if stem.endswith(suffix):
            return True
    return False


def group_fits_by_prefix(directory):
    """
    Scan *directory* for FITS files and bucket them by the first
    PREFIX_LENGTH characters of the filename.

    Skips:
      - files produced by a previous run of this script (_stack, _stack_denoised)
      - files inside _grp_* subdirectories (temp working dirs)

    Returns dict { prefix_string: [Path, ...] }
    """
    groups = defaultdict(list)
    for p in sorted(directory.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in FITS_EXTENSIONS:
            continue
        # Skip our own output files so re-runs don't stack stacks
        if is_output_file(p):
            continue
        if len(p.name) >= PREFIX_LENGTH:
            prefix = p.name[:PREFIX_LENGTH]
        else:
            prefix = "_ungrouped_"
        groups[prefix].append(p)
    return dict(groups)


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


def process_group(siril, group_prefix, files, work_dir):
    """
    Run the full register -> stack -> denoise pipeline for one prefix group.
    Returns True on success, False if a critical step failed.
    """
    n = len(files)
    siril_log(siril, "")
    siril_log(siril, "=" * 60)
    siril_log(siril, "Group: " + group_prefix + "  (" + str(n) + " file(s))")
    siril_log(siril, "=" * 60)

    if n < 2:
        siril_log(siril, "  Skipping: need at least 2 frames to align and stack (found " + str(n) + ").")
        return False

    # ------------------------------------------------------------------
    # Build names. Each group gets its own clean temp directory so
    # leftover files from a previous run can never bleed into this one.
    # ------------------------------------------------------------------
    safe_prefix  = "".join(c if (c.isalnum() or c == "_") else "_" for c in group_prefix)
    group_dir    = work_dir / ("_grp_" + safe_prefix)

    # Always start with a completely empty directory to prevent stale
    # symlinks / converted files from a prior run inflating the file count.
    if group_dir.exists():
        import shutil as _shutil
        _shutil.rmtree(group_dir, ignore_errors=True)
    group_dir.mkdir(parents=True, exist_ok=True)

    seq_name      = safe_prefix
    reg_seq_name  = "r_" + safe_prefix
    stack_out     = safe_prefix + "_stack"
    denoised_out  = safe_prefix + "_stack_denoised"

    # ------------------------------------------------------------------
    # Step 1: Populate the group sub-directory and convert to sequence.
    # We also tell Siril which extension to use (setext) so that convert
    # and register agree on the filename suffix -- without this, convert
    # may write .fit while register looks for .fits (or vice-versa).
    # ------------------------------------------------------------------
    siril_log(siril, "  [1/4] Converting " + str(n) + " files into sequence '" + seq_name + "'...")

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
    # register without -2pass writes the r_ image files directly (one pass).
    # -2pass only computes transforms into the .seq without writing images,
    # and would require a separate seqapplyreg step before stacking.
    # Single-pass register is correct for unattended batch use.
    # ------------------------------------------------------------------
    siril_log(siril, "  [2/4] Registering (-transf=" + REGISTER_TRANSF + ")...")
    if not cmd_safe(siril, "register", seq_name, "-transf=" + REGISTER_TRANSF):
        siril_log(siril, "  [ERROR] registration failed -- skipping group.")
        return False

    # ------------------------------------------------------------------
    # Step 3: Stack
    # Correct syntax: stack seqname rej sigma_low sigma_high -norm= -out=
    # Rejection type and sigmas are positional (no "type=" prefix needed).
    # Confirmed from official docs: stack bias rej 3 3 -nonorm -out=master-bias
    # ------------------------------------------------------------------
    siril_log(siril, "  [3/4] Stacking -> " + stack_out + " ...")
    if not cmd_safe(
        siril,
        "stack", reg_seq_name,
        STACK_TYPE,
        str(STACK_SIGMA_LOW),
        str(STACK_SIGMA_HIGH),
        "-norm=" + STACK_NORM,
        "-out=" + stack_out,
    ):
        siril_log(siril, "  [ERROR] stacking failed -- skipping denoising.")
        return False

    # ------------------------------------------------------------------
    # Step 4: GraXpert denoising via pyscript
    # GraXpert-AI.py CLI v2+ uses flag arguments, not key=value pairs.
    # Correct usage (from the script's own --help output):
    #   pyscript GraXpert-AI.py -denoise [-strength=<0.0-1.0>]
    # The script operates on the currently loaded Siril image and updates
    # it in place -- no -output argument exists.  We load the stack first,
    # call pyscript, then save the (now-denoised) current image ourselves.
    # pyscript blocks until completion when called from inside a script.
    # ------------------------------------------------------------------
    siril_log(siril, "  [4/4] Denoising via GraXpert-AI.py -denoise (strength=" + str(DENOISE_STRENGTH) + ")...")

    # Find the stacked file (Siril writes .fit or .fits depending on setext)
    stack_path = None
    for ext in (".fit", ".fits", ".fts"):
        candidate = group_dir / (stack_out + ext)
        if candidate.exists():
            stack_path = candidate
            break

    if stack_path is None:
        siril_log(siril, "  [ERROR] Stacked file not found -- skipping denoise.")
        cleanup_group_dir(siril, group_dir, work_dir)
        return False

    # Load the stack so it becomes Siril's current image
    if not cmd_safe(siril, "load", str(stack_path)):
        siril_log(siril, "  [ERROR] Could not load stacked file.")
        cleanup_group_dir(siril, group_dir, work_dir)
        return False

    # Run GraXpert-AI.py in denoise mode -- modifies the current Siril image
    denoise_ok = cmd_safe(
        siril,
        "pyscript", "GraXpert-AI.py",
        "-denoise",
        "-strength=" + str(DENOISE_STRENGTH),
    )

    # Save whichever image is now current (denoised or original on fallback)
    final_path = work_dir / ((denoised_out if denoise_ok else stack_out) + ".fits")
    if not cmd_safe(siril, "save", str(final_path)):
        siril_log(siril, "  [ERROR] Could not save result to " + str(final_path))
        cleanup_group_dir(siril, group_dir, work_dir)
        return False

    label = "denoised" if denoise_ok else "plain stack (denoise failed)"
    siril_log(siril, "  OK  Saved (" + label + "): " + final_path.name)

    # Clean up the temporary group directory
    cleanup_group_dir(siril, group_dir, work_dir)
    return True


def main():
    siril = s.SirilInterface()

    try:
        siril.connect()
        siril_log(siril, "GalacticStack-AI v1.1.0 connected.")
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
        work_dir = Path(siril.get_siril_wd())
        siril_log(siril, "Working directory: " + str(work_dir))
        siril_log(siril, "Grouping by first " + str(PREFIX_LENGTH) + " characters of filename...")

        groups = group_fits_by_prefix(work_dir)

        if not groups:
            siril_log(siril, "No FITS files found. Set the Siril working directory to")
            siril_log(siril, "the folder containing your renamed FITS files and try again.")
            siril.disconnect()
            return

        siril_log(siril, "Found " + str(len(groups)) + " group(s):")
        for prefix, files in groups.items():
            siril_log(siril, "  " + prefix + "  ->  " + str(len(files)) + " file(s)")

        ok = fail = skip = 0
        for prefix, files in groups.items():
            if prefix == "_ungrouped_":
                siril_log(siril, "Skipping " + str(len(files)) + " ungrouped file(s).")
                skip += len(files)
                continue
            if process_group(siril, prefix, files, work_dir):
                ok += 1
            else:
                fail += 1

        # Restore working directory to the root folder when done
        cmd_safe(siril, "cd", str(work_dir))

        siril_log(siril, "")
        siril_log(siril, "=" * 60)
        siril_log(siril, "GalacticStack-AI complete.")
        siril_log(siril, "  Groups processed OK : " + str(ok))
        siril_log(siril, "  Groups with errors  : " + str(fail))
        if skip:
            siril_log(siril, "  Ungrouped files skipped: " + str(skip))
        siril_log(siril, "=" * 60)

    except Exception as exc:
        siril_log(siril, "Unhandled error: " + str(exc))
        traceback.print_exc()

    finally:
        siril.disconnect()


# ---------------------------------------------------------------------------
# Siril executes scripts via exec(), so __name__ is NOT '__main__'.
# Call main() unconditionally at module level so it always runs.
# ---------------------------------------------------------------------------
main()