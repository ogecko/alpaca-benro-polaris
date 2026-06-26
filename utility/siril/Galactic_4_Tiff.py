# SPDX-License-Identifier: GPL-3.0-or-later
# Galactic_4_Tiff.py
# Version: 1.1.0
# Part of the Galactic pipeline for panoramic astrophotography automation.
#
# Description
# -----------
# Converts every FITS file in result_fits/ to a 16-bit TIFF in result_tiff/.
# No filename filtering or skip logic -- simply converts everything present.
# Fast enough to rerun whenever needed after any final manual adjustments.
#
# Usage
# -----
#   Make any final manual adjustments to result_fits/*.fits
#   Run from Scripts menu -- all FITS are converted, previous TIFFs overwritten.

import sirilpy as s
import traceback
from pathlib import Path

FITS_EXTENSIONS = {".fits", ".fit", ".fts"}


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


def main():
    siril = s.SirilInterface()
    try:
        siril.connect()
        siril_log(siril, "Galactic_4_Tiff v1.1.0 connected.")
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

        if not fits_dir.is_dir():
            siril_log(siril, "[ERROR] result_fits/ not found -- run Galactic_3_Stretch.py first.")
            siril.disconnect()
            return

        tiff_dir.mkdir(exist_ok=True)

        fits_files = sorted(p for p in fits_dir.iterdir()
                            if p.is_file() and p.suffix.lower() in FITS_EXTENSIONS)

        if not fits_files:
            siril_log(siril, "No FITS files found in result_fits/.")
            siril.disconnect()
            return

        siril_log(siril, "Converting " + str(len(fits_files))
                  + " file(s) from result_fits/ -> result_tiff/ ...")

        ok = fail = 0
        for fits_path in fits_files:
            tiff_path = tiff_dir / (fits_path.stem + ".tif")
            if not cmd_safe(siril, "load", str(fits_path)):
                siril_log(siril, "  [ERROR] Cannot load " + fits_path.name)
                fail += 1
                continue
            if cmd_safe(siril, "savetif", str(tiff_path.with_suffix(""))):
                siril_log(siril, "  " + fits_path.name + " -> " + tiff_path.name)
                ok += 1
            else:
                siril_log(siril, "  [ERROR] TIFF save failed: " + fits_path.name)
                fail += 1

        cmd_safe(siril, "cd", str(home_dir))

        siril_log(siril, " ")
        siril_log(siril, "=" * 60)
        siril_log(siril, "Galactic_4_Tiff complete.")
        siril_log(siril, "  OK  : " + str(ok)
                  + "   FAIL: " + str(fail)
                  + "   TOTAL: " + str(ok + fail))
        siril_log(siril, "  TIFFs saved to result_tiff/ -- ready for stitching.")
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