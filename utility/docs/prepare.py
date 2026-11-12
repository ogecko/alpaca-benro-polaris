"""
Stage the repo's Markdown docs for the Zensical documentation site.

The docs are written to read well on github.com: README.md lives at the repo root, and every
page in docs/ starts with a hand-made nav bar linking back to ../README.md. Zensical can only
see files inside its docs_dir and builds its own navigation, so this copies docs/ into
build/site-src/ (the docs_dir in zensical.toml) and adjusts the copy, never the originals:

  * README.md becomes index.md, with its ./docs/ links and image paths made relative to docs/,
    and its links to other repo files (e.g. ./LICENSE) pointing at github.com
  * the github.com nav bar on line 1 of each page is dropped (Zensical's sidebar replaces it)
  * links to ../README.md point at index.md
  * links to other repo files outside docs/ (e.g. ../utility/ccdciel) point at github.com
  * lists are reshaped from github.com's lenient layout to Python-Markdown's (see fix_lists)
  * internal working notes (EXCLUDE) are left out

Only files whose staged content would change are rewritten, so a live preview rebuilds just
the pages you edited.

Usage (from the repo root):
    uv run --group docs python utility/docs/prepare.py            # stage once, then:
    uv run --group docs zensical build                            # static site in site/
    uv run --group docs python utility/docs/prepare.py --serve    # stage, watch docs/ + README.md,
        # and run the live preview at http://localhost:8000/alpaca-benro-polaris/
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'docs'
README = ROOT / 'README.md'
DEST = ROOT / 'build' / 'site-src'
REPO_BLOB = 'https://github.com/ogecko/alpaca-benro-polaris/blob/main/'

EXCLUDE = {'todo.md'}
POLL_SECONDS = 0.5

NAV_BAR = re.compile(r'^\[Home\]\([^)]*README\.md\).*\n+')
README_LINK = re.compile(r'\]\(\.\./README\.md(#[^)]*)?\)')
OUTSIDE_LINK = re.compile(r'\]\(\.\./([^)]+)\)')
LIST_ITEM = re.compile(r'^( *)([-*+]|\d+[.)]) +\S')
FENCE = re.compile(r'^ *(```|~~~)')
BLOCK_START = re.compile(r'^(#|\||>|<|```|~~~|---|\*\*\*|___)')  # can't be a lazy continuation of a list item
INDENT_STEP = 4


def fix_lists(text: str) -> str:
    """
    Convert github.com (CommonMark) list layout to what Python-Markdown accepts:
      * a list must follow a blank line -- github.com lets one start straight after a paragraph
      * each nesting level must be indented 4 spaces -- github.com accepts 2 or 3
    Item continuation lines and fenced code inside items are shifted with their item.
    """
    out: list[str] = []
    stack: list[tuple[int, int, int]] = []  # open items: (src marker indent, src content indent, new content indent)
    fence_shift = None                      # indent shift applied to every line of the open code fence
    prev_blank, prev_item = True, False
    loose = False                           # a blank line or code fence since the last item: the next sibling needs a blank line

    for line in text.expandtabs(INDENT_STEP).split('\n'):
        if fence_shift is not None:
            if line.strip():
                line = ' ' * max(0, len(line) - len(line.lstrip()) + fence_shift) + line.lstrip()
            if FENCE.match(line):
                fence_shift = None
                loose = True
            out.append(line)
            continue

        if not line.strip():
            out.append(line)
            prev_blank, prev_item = True, False
            loose = loose or bool(stack)
            continue

        indent = len(line) - len(line.lstrip())
        item = LIST_ITEM.match(line)
        if stack and not item and indent == 0 and (prev_blank or BLOCK_START.match(line)):
            stack.clear()                  # unindented text after a blank line, or a heading etc, ends the list

        shift = 0
        if item:
            sibling = False
            while stack and stack[-1][0] >= indent:
                sibling = sibling or stack[-1][0] == indent
                stack.pop()
            if not prev_blank and not prev_item and (not sibling or loose):
                out.append('')             # a list starting straight after text, or the next item of a loose one
            loose = False
            new_indent = stack[-1][2] if stack else 0
            stack.append((indent, item.end() - 1, new_indent + INDENT_STEP))
            line = ' ' * new_indent + line.lstrip()
        elif stack and indent:             # an item's continuation line (indent 0 is a lazy continuation)
            while len(stack) > 1 and indent <= stack[-1][0]:
                stack.pop()
            _, src_content, new_content = stack[-1]
            shift = new_content - src_content
            line = ' ' * max(new_content, indent + shift) + line.lstrip()

        if FENCE.match(line):
            fence_shift = shift
        out.append(line)
        prev_blank, prev_item = False, bool(item)
    return '\n'.join(out)


def fix_page(text: str) -> str:
    text = NAV_BAR.sub('', text, count=1)
    text = README_LINK.sub(lambda m: f'](index.md{m.group(1) or ""})', text)
    text = OUTSIDE_LINK.sub(lambda m: f']({REPO_BLOB}{m.group(1)})', text)
    return fix_lists(text)


def fix_readme(text: str) -> str:
    text = NAV_BAR.sub('', text, count=1)
    text = text.replace('](./README.md)', '](index.md)')
    text = re.sub(r'\]\((?:\./)?docs/', '](', text)
    text = re.sub(r'(src=["\'])(?:\./)?docs/', r'\1', text)
    text = re.sub(r'\]\(\./(?!README\.md)([^)]+)\)', rf']({REPO_BLOB}\1)', text)  # other repo files, e.g. ./LICENSE
    return fix_lists(text)


def source_files() -> dict[Path, Path]:
    """Map each staged path to the source file it comes from."""
    files = {DEST / 'index.md': README}
    for src in SRC.rglob('*'):
        if src.is_file() and src.name not in EXCLUDE:
            files[DEST / src.relative_to(SRC)] = src
    return files


def stage_file(dest: Path, src: Path) -> bool:
    """Write one staged file if its content changed. Returns True if it was written."""
    if src.suffix == '.md':
        text = src.read_text(encoding='utf-8')
        text = fix_readme(text) if src == README else fix_page(text)
        if dest.exists() and dest.read_text(encoding='utf-8') == text:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding='utf-8')
        return True
    if dest.exists() and dest.stat().st_size == src.stat().st_size and dest.stat().st_mtime >= src.stat().st_mtime:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def sync() -> list[Path]:
    """Bring DEST in line with the sources. Returns the source files that were (re)staged."""
    files = source_files()
    changed = [src for dest, src in files.items() if stage_file(dest, src)]
    if DEST.exists():
        for stale in [p for p in DEST.rglob('*') if p.is_file() and p not in files]:
            stale.unlink()
            changed.append(stale)
    return changed


def snapshot() -> dict[Path, float]:
    return {src: src.stat().st_mtime for src in source_files().values()}


def serve() -> None:
    """Run zensical serve, re-staging whenever a source file is added, edited or removed."""
    zensical = subprocess.Popen(['uv', 'run', '--group', 'docs', 'zensical', 'serve'], cwd=ROOT)
    seen = snapshot()
    try:
        while zensical.poll() is None:
            time.sleep(POLL_SECONDS)
            now = snapshot()
            if now != seen:
                seen = now
                for path in sync():
                    print(f'staged {path.relative_to(ROOT)}')
    except KeyboardInterrupt:
        pass
    finally:
        zensical.terminate()


def main() -> None:
    changed = sync()
    print(f'Staged {len(changed)} changed files in {DEST.relative_to(ROOT)}')
    if '--serve' in sys.argv:
        serve()


if __name__ == '__main__':
    main()
