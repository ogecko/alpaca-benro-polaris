"""
Add one version of the built documentation site to the tree published on GitHub Pages.

Every release keeps its own copy of the docs, in the layout used by mike (which Zensical's
version selector understands):

  <pages>/v2.2/...       one folder per version, replaced each time that version is published
  <pages>/versions.json  the versions listed in the selector, newest first
  <pages>/index.html     redirects the site root to the newest version
  <pages>/sitemap.xml    a sitemap index pointing search engines at each version's sitemap.xml
  <pages>/<file>         any files in an optional root folder (e.g. docs/site-root), such as the
                         Google Search Console verification file, which must sit at the site root

The pages tree is a checkout of the gh-pages branch, so older versions survive between builds.

Usage (from the repo root):
    MIKE_DOCS_VERSION=v2.2 uv run --group docs zensical build --clean      # builds pilot/dist/docs
    python utility/docs/publish_version.py pilot/dist/docs <gh-pages checkout> v2.2 [docs/site-root]
"""
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

VERSION = re.compile(r'^v(\d+)\.(\d+)$')
CONFIG = Path(__file__).resolve().parents[2] / 'zensical.toml'

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

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}</sitemapindex>
"""


def site_url() -> str:
    """The site root URL from zensical.toml, e.g. https://ogecko.github.io/alpaca-benro-polaris/"""
    url = tomllib.loads(CONFIG.read_text(encoding='utf-8'))['project']['site_url']
    return url if url.endswith('/') else url + '/'


def sitemap_index(versions: list[str]) -> str:
    base = site_url()
    entries = ''.join(f'  <sitemap>\n    <loc>{base}{v}/sitemap.xml</loc>\n  </sitemap>\n' for v in versions)
    return SITEMAP_INDEX.format(entries=entries)


def version_key(version: str) -> tuple[int, int]:
    major, minor = VERSION.match(version).groups()
    return int(major), int(minor)


def publish(site: Path, pages: Path, version: str, root_files: Path | None = None) -> None:
    if not VERSION.match(version):
        sys.exit(f'version must look like v2.2, not {version!r}')

    shutil.rmtree(pages / version, ignore_errors=True)
    shutil.copytree(site, pages / version)

    versions = sorted({p.name for p in pages.iterdir() if p.is_dir() and VERSION.match(p.name)}, key=version_key, reverse=True)
    entries = [{'version': v, 'title': v, 'aliases': []} for v in versions]
    (pages / 'versions.json').write_text(json.dumps(entries, indent=2) + '\n', encoding='utf-8')
    (pages / 'index.html').write_text(REDIRECT.format(version=versions[0]), encoding='utf-8')
    (pages / 'sitemap.xml').write_text(sitemap_index(versions), encoding='utf-8')
    (pages / '.nojekyll').touch()
    if root_files:
        for f in root_files.iterdir():
            if f.is_file():
                shutil.copy2(f, pages / f.name)
    print(f'Published {version}; site root redirects to {versions[0]}; versions: {", ".join(versions)}')


if __name__ == '__main__':
    publish(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]) if len(sys.argv) > 4 else None)
