#!/usr/bin/env python3

import os
import sys

RENAME_MAP = {
    "LIGHT": "lights",
    "DARK": "darks",
    "BIAS": "biases",
    "FLAT": "flats",
}

def rename_directories(root_dir):
    for current_path, dirnames, filenames in os.walk(root_dir, topdown=False):
        for dirname in dirnames:
            if dirname in RENAME_MAP:
                old_path = os.path.join(current_path, dirname)
                new_name = RENAME_MAP[dirname]
                new_path = os.path.join(current_path, new_name)

                if os.path.exists(new_path):
                    print(f"Skipping (target exists): {new_path}")
                    continue

                print(f"Renaming: {old_path} -> {new_path}")
                os.rename(old_path, new_path)


def main():
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python rename_dirs.py <images_directory>")
        print()
        print("Description:")
        print("  Recursively scans <images_directory> and renames NINA image")
        print("  subdirectories to match Siril script expectations.")
        print()
        print("  The following directory names are converted:")
        print("      LIGHT  -> lights")
        print("      DARK   -> darks")
        print("      BIAS   -> biases")
        print("      FLAT   -> flats")
        print()
        print("Example:")
        print("  python rename_dirs.py /astro/images")
        print()
        sys.exit(1)

    root_dir = sys.argv[1]

    if not os.path.isdir(root_dir):
        print(f"Error: '{root_dir}' is not a valid directory.")
        sys.exit(1)

    rename_directories(root_dir)
    print("Done.")


if __name__ == "__main__":
    main()