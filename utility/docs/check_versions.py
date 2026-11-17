"""
Check the docs version matches the driver and Pilot versions.

The docs version is set once, as docs_version in zensical.toml (e.g. "v2.2"), and the online docs
and offline docs zip (release docs-v2.2) are published under it. Two other places work out the same
version from their own version number, so must agree with it:
  * driver/shr.py DeviceMetadata.Version ("2.2.0 Release"): the driver downloads and serves the
    offline docs for this version (driver/app_web.py)
  * pilot/package.json version ("2.2.0"): Pilot links to the online docs for this version
    (pilot/src/stores/ui.ts)

Usage (from the repo root):
    python utility/docs/check_versions.py      # exits 1 if they differ
"""
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def major_minor(version: str) -> str:
    match = re.match(r'v?(\d+)\.(\d+)', version)
    if not match:
        sys.exit(f'Unrecognised version: {version!r}')
    return f'v{match[1]}.{match[2]}'


def main() -> None:
    docs = tomllib.loads((ROOT / 'zensical.toml').read_text(encoding='utf-8'))['project']['extra']['docs_version']
    shr = re.search(r"^\s*Version\s*=\s*'([^']+)'", (ROOT / 'driver' / 'shr.py').read_text(encoding='utf-8'), re.M)
    if not shr:
        sys.exit('DeviceMetadata.Version not found in driver/shr.py')
    pilot = json.loads((ROOT / 'pilot' / 'package.json').read_text(encoding='utf-8'))['version']

    found = {
        'zensical.toml docs_version': docs,
        'driver/shr.py Version': shr[1],
        'pilot/package.json version': pilot,
    }
    if len({major_minor(v) for v in found.values()}) > 1:
        for where, version in found.items():
            print(f'{where}: {version!r} -> {major_minor(version)}')
        print('The docs version must match the driver and Pilot versions (major.minor).')
        sys.exit(1)


if __name__ == '__main__':
    main()
