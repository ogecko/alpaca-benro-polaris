#!/usr/bin/env python3
"""
fits_add_galactic.py
--------------------
Reads all FITS files in a directory, converts RA/Dec from the header to
Galactic coordinates (l, b) using pyephem, and writes GLON / GLAT back
into the header so ASTAP can read them.

Usage:
    python fits_add_galactic.py DIRECTORY [options]

Arguments:
    directory       Folder containing .fits / .fit / .fts files.

Options:
    --decimals N    Decimal places for GLON/GLAT values (default: 5).
                    Values are zero-padded:  GLON → "007.12345"
                                             GLAT → "07.12345 N" or "07.12345 S"
    --suffix TEXT   Append TEXT to output filenames before the extension.
                    Default: edit files in-place.
    --rename        Prefix each file with GLATNNNX_GLONNN_ (0 decimal places).
                    e.g. GLAT007S_GLON209_Light_001.fits
    --dry-run       Show what would be done without writing anything.
    --recurse       Also search sub-directories.
    --overwrite     Re-write GLON/GLAT even if already present in the header.

Output header keywords (readable by ASTAP):
    GLON  – Galactic longitude, stored as float, comment shows padded string
    GLAT  – Galactic latitude,  stored as float, comment shows padded string + N/S
"""

import argparse
import math
import sys
from pathlib import Path

import ephem
from astropy.io import fits

# ---------------------------------------------------------------------------
# RA/Dec keyword candidates, tried in priority order.
# ---------------------------------------------------------------------------
RA_KEYS_DEG  = ["RA",      "RA_OBJ",  "CRVAL1"]   # decimal degrees (float)
DEC_KEYS_DEG = ["DEC",     "DEC_OBJ", "CRVAL2"]   # decimal degrees (float)
RA_KEYS_STR  = ["OBJCTRA"]                         # HH:MM:SS.s string
DEC_KEYS_STR = ["OBJCTDEC"]                        # ±DD:MM:SS.s string

FITS_EXTENSIONS = {".fits", ".fit", ".fts"}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_glon(val: float, decimals: int) -> str:
    """
    Format Galactic longitude for display / FITS comment.
    Always 3 integer digits, zero-padded.
      decimals=5 →  "007.12345"
      decimals=0 →  "007"
    """
    # Keep in [0, 360)
    val = val % 360.0
    if decimals > 0:
        width = 3 + 1 + decimals          # e.g. "007.12345" = 9 chars
        return f"{val:0{width}.{decimals}f}"
    else:
        return f"{int(round(val)) % 360:03d}"


def format_glat(val: float, decimals: int) -> str:
    """
    Format Galactic latitude for display / FITS comment.
    Always 2 integer digits, zero-padded, with N (≥0) or S (<0) suffix.
      decimals=5, val=-7.123  →  "07.12300 S"
      decimals=0, val=57.9    →  "58 N"
    """
    suffix  = "S" if val < 0 else "N"
    abs_val = abs(val)
    if decimals > 0:
        width = 2 + 1 + decimals           # e.g. "07.12300" = 8 chars
        num   = f"{abs_val:0{width}.{decimals}f}"
    else:
        num = f"{int(round(abs_val)):02d}"
    return f"{num} {suffix}"


def rename_prefix(l: float, b: float) -> str:
    """
    Build the filename prefix used by --rename.
    Always uses 0 decimal places (integer) with zero-padding.
      l=209.456, b=-7.123  →  "GLAT007S_GLON209_"
      l=359.94,  b=-0.037  →  "GLAT000S_GLON000_"
    """
    glat_int = int(round(abs(b)))
    glon_int  = int(round(l)) % 360
    ns = "S" if b < 0 else "N"
    return f"GLAT{glat_int:03d}{ns}_GLON{glon_int:03d}_"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def sanitize_path(raw: str) -> Path:
    """
    Strip surrounding quotes, trailing backslashes, and whitespace.
    Handles the three most common Windows copy-paste problems:
      1. Explorer's "Copy as path" wraps the path in double-quotes.
      2. A trailing backslash causes cmd.exe to mis-parse the closing quote.
      3. Invisible trailing spaces added during copy-paste.
    """
    p = raw.strip()
    if len(p) >= 2 and p[0] in ('"', "'") and p[-1] == p[0]:
        p = p[1:-1]
    p = p.rstrip('/\\ \t')
    return Path(p)


def find_fits_files(directory: Path, recurse: bool) -> list:
    """Return sorted list of FITS files in *directory*."""
    pattern = "**/*" if recurse else "*"
    return sorted(
        p for p in directory.glob(pattern)
        if p.is_file() and p.suffix.lower() in FITS_EXTENSIONS
    )


# ---------------------------------------------------------------------------
# Coordinate extraction
# ---------------------------------------------------------------------------

def extract_ra_dec(header):
    """
    Pull RA and Dec from a FITS header.
    Returns (ra_deg, dec_deg) as floats, or None if not found.
    """
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
                    ra_deg = math.degrees(ephem.hours(str(header[key]))); break
                except (ValueError, TypeError):
                    pass

    if dec_deg is None:
        for key in DEC_KEYS_STR:
            if key in header:
                try:
                    dec_deg = math.degrees(ephem.degrees(str(header[key]))); break
                except (ValueError, TypeError):
                    pass

    if ra_deg is None or dec_deg is None:
        return None
    if not (0.0 <= ra_deg < 360.0):
        return None
    if not (-90.0 <= dec_deg <= 90.0):
        return None

    return ra_deg, dec_deg


def radec_to_galactic(ra_deg: float, dec_deg: float):
    """Convert equatorial (J2000) to Galactic (l, b) in degrees via pyephem."""
    eq  = ephem.Equatorial(math.radians(ra_deg), math.radians(dec_deg), epoch=ephem.J2000)
    gal = ephem.Galactic(eq)
    l   = math.degrees(float(gal.lon)) % 360.0
    b   = math.degrees(float(gal.lat))
    return l, b


# ---------------------------------------------------------------------------
# Core file processor
# ---------------------------------------------------------------------------

def process_file(
    fits_path: Path,
    decimals: int,
    suffix: str,
    rename: bool,
    dry_run: bool,
    overwrite: bool,
) -> str:
    """Process a single FITS file. Returns a one-line status string."""
    try:
        mode = "readonly" if (suffix or rename or dry_run) else "update"
        with fits.open(fits_path, mode=mode) as hdul:
            header = hdul[0].header

            if "GLON" in header and "GLAT" in header and not overwrite:
                return f"SKIP (already has GLON/GLAT): {fits_path.name}"

            coords = extract_ra_dec(header)
            if coords is None:
                return f"SKIP (no RA/Dec found):        {fits_path.name}"

            ra_deg, dec_deg = coords
            l, b = radec_to_galactic(ra_deg, dec_deg)

            glon_str = format_glon(l, decimals)
            glat_str = format_glat(b, decimals)

            if dry_run:
                prefix = rename_prefix(l, b) if rename else ""
                new_name = prefix + fits_path.name if rename else fits_path.name
                return (
                    f"DRY-RUN: {fits_path.name}"
                    + (f" → {new_name}" if rename else "")
                    + f"  GLON={glon_str}  GLAT={glat_str}"
                )

            # Build the header values: float stored as value, formatted string in comment
            glon_val = round(l, decimals)
            glat_val = round(b, decimals)
            glon_comment = f"{glon_str} deg Gal.lon J2000"
            glat_comment = f"{glat_str} deg Gal.lat J2000"

            if suffix:
                # New file with suffix appended to stem
                out_path = fits_path.with_name(fits_path.stem + suffix + fits_path.suffix)
                hdul[0].header["GLON"] = (glon_val, glon_comment)
                hdul[0].header["GLAT"] = (glat_val, glat_comment)
                hdul.writeto(out_path, overwrite=True)
                return f"OK  {fits_path.name} → {out_path.name}  GLON={glon_str}  GLAT={glat_str}"

            elif rename:
                # New file with GLAT/GLON prefix; original left untouched
                prefix   = rename_prefix(l, b)
                out_path = fits_path.with_name(prefix + fits_path.name)
                hdul[0].header["GLON"] = (glon_val, glon_comment)
                hdul[0].header["GLAT"] = (glat_val, glat_comment)
                hdul.writeto(out_path, overwrite=True)
                return f"OK  {fits_path.name} → {out_path.name}  GLON={glon_str}  GLAT={glat_str}"

            else:
                # Edit in-place
                hdul[0].header["GLON"] = (glon_val, glon_comment)
                hdul[0].header["GLAT"] = (glat_val, glat_comment)
                hdul.flush()
                return f"OK  {fits_path.name}  GLON={glon_str}  GLAT={glat_str}"

    except Exception as exc:
        return f"ERROR {fits_path.name}: {exc}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Add Galactic coordinates (GLON/GLAT) to FITS headers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "directory",
        type=str,
        help="Folder containing FITS files",
    )
    parser.add_argument(
        "--decimals",
        type=int,
        default=5,
        metavar="N",
        help="Decimal places for GLON/GLAT (default: 5). 0 = integers only.",
    )
    parser.add_argument(
        "--suffix",
        default="",
        help='Append TEXT to output filenames, e.g. "_gal". Default: edit in-place.',
    )
    parser.add_argument(
        "--rename",
        action="store_true",
        help=(
            "Write a new copy of each file prefixed with GLATNNNX_GLONNN_. "
            "The prefix always uses 0 decimal places. Original files are untouched."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing anything.",
    )
    parser.add_argument(
        "--recurse",
        action="store_true",
        help="Also search sub-directories.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-write GLON/GLAT even if already present in the header.",
    )
    args = parser.parse_args()

    if args.decimals < 0:
        print("ERROR: --decimals must be 0 or greater.", file=sys.stderr)
        sys.exit(1)

    if args.suffix and args.rename:
        print("ERROR: --suffix and --rename cannot be used together.", file=sys.stderr)
        sys.exit(1)

    directory = sanitize_path(args.directory)

    if not directory.is_dir():
        print(f"ERROR: '{directory}' is not a directory.", file=sys.stderr)
        print(
            "  Tip: if you copied the path from Windows Explorer, check for:\n"
            "    - Surrounding quotes  (remove them, or use right-click > Copy as path)\n"
            "    - A trailing backslash  e.g. D:\\Images\\  →  D:\\Images\n"
            "    - Trailing spaces or invisible characters\n"
            "  Example:  python fits_add_galactic.py D:\\Images\\2026-06-22\\L\\process",
            file=sys.stderr,
        )
        sys.exit(1)

    files = find_fits_files(directory, args.recurse)
    if not files:
        print("No FITS files found.")
        sys.exit(0)

    print(f"Found {len(files)} FITS file(s) in '{directory}'")
    print(f"Decimals: {args.decimals}  |  Rename: {args.rename}  |  Suffix: '{args.suffix}'\n")

    ok = skip = error = 0
    for fits_path in files:
        result = process_file(
            fits_path,
            decimals=args.decimals,
            suffix=args.suffix,
            rename=args.rename,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
        print(result)
        if result.startswith("OK"):
            ok += 1
        elif result.startswith("ERROR"):
            error += 1
        else:
            skip += 1

    print(f"\nDone.  OK={ok}  Skipped={skip}  Errors={error}")


if __name__ == "__main__":
    main()