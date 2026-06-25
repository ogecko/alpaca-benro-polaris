# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_1_Stack.py
# Version: 1.1.0
# Author:  Generated for alpaca-benro-polaris utility suite
# Contact: https://github.com/scriptable
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
DENOISE_STRENGTH = 0.5      # GraXpert denoising strength: 0.0 (none) to 1.0 (max)
REGISTER_TRANSF  = "homography" # registration transform: shift / similarity / affine / homography
STACK_TYPE       = "rej"    # stacking type (rej = sigma-clipping rejection)
STACK_SIGMA_LOW  = 3        # lower sigma threshold for rejection
STACK_SIGMA_HIGH = 3        # upper sigma threshold for rejection
STACK_NORM       = "addscale"  # normalisation: addscale / add / mul / no
FITS_EXTENSIONS  = {".fits", ".fit", ".fts"}
PREFIX_LENGTH    = 16       # number of filename characters used to group files

# Channel subdirectories to scan (relative to Siril home directory).
# Stacked outputs are saved back into the same directory they were found in
# so that Galactic_2_Recompose.py can find them in channel/stacked/.
# Only directories that exist are processed -- missing filters are skipped.
CHANNEL_DIRS = ["L/stacked", "R/stacked", "G/stacked", "B/stacked",
                "Ha/stacked", "Sii/stacked", "Oiii/stacked"]
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

# Prefixes that identify intermediate files from Galactic_0_Calibration.py.
# light_NNNNN.fits files are created by `convert` in the process/ directory
# (calibration output). They live in channel/process/ not channel/stacked/.
# and should never be picked up as input frames for stacking.
INTERMEDIATE_PREFIXES = ("light_", "flat_", "dark_", "bias_",
                         "pp_flat_", "pp_dark_", "pp_bias_")


def is_output_file(path):
    """Return True if *path* looks like a file this script already produced
    or an intermediate calibration file that should be excluded."""
    stem = path.stem
    # Skip our own stack output files
    for suffix in OUTPUT_SUFFIXES:
        if stem.endswith(suffix):
            return True
    # Skip intermediate convert/calibrate files from Galactic_0_Calibration
    for prefix in INTERMEDIATE_PREFIXES:
        if stem.startswith(prefix):
            return True
    return False


def group_fits_by_channel(home_dir):
    """
    Scan each channel's process/ subdirectory for FITS input files and group
    them by the first PREFIX_LENGTH characters of the filename.

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
            prefix = p.name[:PREFIX_LENGTH] if len(p.name) >= PREFIX_LENGTH else "_ungrouped_"
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
        # Single frame -- skip stacking/registration but copy it through
        # so downstream scripts (Galactic_2_Recompose) can find it.
        siril_log(siril, "  Single frame -- copying as stack_denoised (no stacking possible).")
        safe_prefix  = "".join(c if (c.isalnum() or c == "_") else "_" for c in group_prefix)
        denoised_out = safe_prefix + "_stack_denoised"
        # Check skip first
        for ext in (".fits", ".fit", ".fts"):
            existing = work_dir / (denoised_out + ext)
            if existing.exists():
                siril_log(siril, "  SKIP: output already exists: " + existing.name)
                return True
        src_file = files[0]
        dest_file = work_dir / (denoised_out + src_file.suffix)
        try:
            import shutil as _shutil
            _shutil.copy2(src_file, dest_file)
            siril_log(siril, "  Copied: " + src_file.name + " -> " + dest_file.name)
            return True
        except Exception as exc:
            siril_log(siril, "  [ERROR] Could not copy single frame: " + str(exc))
            return False

    # ------------------------------------------------------------------
    # Build names. Each group gets its own clean temp directory so
    # leftover files from a previous run can never bleed into this one.
    # ------------------------------------------------------------------
    safe_prefix  = "".join(c if (c.isalnum() or c == "_") else "_" for c in group_prefix)
    group_dir    = work_dir / ("_grp_" + safe_prefix)

    seq_name      = safe_prefix
    reg_seq_name  = "r_" + safe_prefix
    stack_out     = safe_prefix + "_stack"
    denoised_out  = safe_prefix + "_stack_denoised"

    # Skip if the denoised output already exists (any extension).
    # Check BEFORE creating the group_dir so no empty directory is left.
    for ext in (".fits", ".fit", ".fts"):
        existing = work_dir / (denoised_out + ext)
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
    # Set the last frame as reference before registering.
    # The first frame can be wobbly due to mount settling after a slew.
    # setref seqname N sets frame N (1-based) as the reference.
    cmd_safe(siril, "setref", seq_name, str(n))
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
        siril_log(siril, "  [3/4] Stacking " + str(n) + " frames -> median"
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
        siril_log(siril, "  [3/4] Stacking " + str(n) + " frames -> "
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
    # Step 4: GraXpert Denoise only
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
        siril_log(siril, "  [ERROR] Stacked file not found -- skipping denoise.")
        cleanup_group_dir(siril, group_dir, work_dir)
        return False

    # Load the stack
    if not cmd_safe(siril, "load", str(stack_path)):
        siril_log(siril, "  [ERROR] Could not load stacked file.")
        cleanup_group_dir(siril, group_dir, work_dir)
        return False

    # Denoise
    siril_log(siril, "  [4/4] Denoising via GraXpert-AI.py -denoise (strength=" + str(DENOISE_STRENGTH) + ")...")
    denoise_ok = cmd_safe(
        siril,
        "pyscript", "GraXpert-AI.py",
        "-denoise",
        "-strength=" + str(DENOISE_STRENGTH),
    )

    # Save result -- named _stack_denoised regardless of which steps succeeded
    # so AlpacaPano-Recompose can find it by its expected filename
    final_path = work_dir / (denoised_out + ".fits")
    if not cmd_safe(siril, "save", str(final_path)):
        siril_log(siril, "  [ERROR] Could not save result to " + str(final_path))
        cleanup_group_dir(siril, group_dir, work_dir)
        return False

    steps_done = ["denoised"] if denoise_ok else ["plain stack"]
    siril_log(siril, "  OK  Saved (" + " + ".join(steps_done) + "): " + final_path.name)

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
        home_dir = Path(siril.get_siril_wd())
        siril_log(siril, "Home directory: " + str(home_dir))
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
                # Check skip before calling so we can count it
                denoised_out = ("".join(c if (c.isalnum() or c == "_") else "_"
                                        for c in prefix) + "_stack_denoised")
                already_done = any((work_dir / (denoised_out + ext)).exists()
                                   for ext in (".fits", ".fit", ".fts"))
                if already_done:
                    skip += 1
                    results.append((channel, prefix, len(files), "SKIP"))
                elif process_group(siril, prefix, files, work_dir):
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
        siril_log(siril, "  Next: plate-solve outputs in stacked/ then run Galactic_2_Recompose.py")
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