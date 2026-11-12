"""
Add one version of the built documentation site to the tree published on GitHub Pages.

Every release keeps its own copy of the docs, in the layout used by mike (which Zensical's
version selector understands):

  <pages>/v2.2/...       one folder per version, replaced each time that version is published
  <pages>/versions.json  the versions listed in the selector, newest first
  <pages>/index.html     redirects the site root to the newest version

The pages tree is a checkout of the gh-pages branch, so older versions survive between builds.

Usage (from the repo root):
    MIKE_DOCS_VERSION=v2.2 uv run --group docs zensical build --clean
    python utility/docs/publish_version.py site <gh-pages checkout> v2.2
"""
import json
import re
import shutil
import sys
from pathlib import Path

VERSION = re.compile(r'^v(\d+)\.(\d+)$')

REDIRECT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Redirecting</title>
  <noscript><meta http-equiv="refresh" content="0; url={version}/"></noscript>
  <script>window.location.replace("{version}/" + window.location.search + window.location.hash);</script>
</head>
<body><a href="{version}/">Alpaca Benro Polaris Driver documentation</a></body>
</html>
"""


def version_key(version: str) -> tuple[int, int]:
    major, minor = VERSION.match(version).groups()
    return int(major), int(minor)


def publish(site: Path, pages: Path, version: str) -> None:
    if not VERSION.match(version):
        sys.exit(f'version must look like v2.2, not {version!r}')

    shutil.rmtree(pages / version, ignore_errors=True)
    shutil.copytree(site, pages / version)

    versions = sorted({p.name for p in pages.iterdir() if p.is_dir() and VERSION.match(p.name)}, key=version_key, reverse=True)
    entries = [{'version': v, 'title': v, 'aliases': []} for v in versions]
    (pages / 'versions.json').write_text(json.dumps(entries, indent=2) + '\n', encoding='utf-8')
    (pages / 'index.html').write_text(REDIRECT.format(version=versions[0]), encoding='utf-8')
    (pages / '.nojekyll').touch()
    print(f'Published {version}; site root redirects to {versions[0]}; versions: {", ".join(versions)}')


if __name__ == '__main__':
    publish(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
