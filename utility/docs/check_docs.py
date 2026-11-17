"""
Check the docs' lists render the same on the documentation site as on github.com.

github.com (CommonMark) is lenient about list layout, but Zensical's Python-Markdown is not:
  * a list must follow a blank line -- github.com lets one start straight after a paragraph
  * each nesting level must be indented 4 spaces -- github.com accepts 2 or 3
A list that breaks these rules looks right on github.com but renders wrongly on the site. The
layout this script writes renders correctly on both.

Usage (from the repo root):
    uv run --group docs python utility/docs/check_docs.py            # list the files that need fixing (exits 1 if any)
    uv run --group docs python utility/docs/check_docs.py --fix      # fix them in place
    uv run --group docs python utility/docs/check_docs.py --version  # print docs_version from zensical.toml
"""
import fnmatch
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs'
CONFIG = tomllib.loads((ROOT / 'zensical.toml').read_text(encoding='utf-8'))['project']
EXCLUDE = (CONFIG.get('exclude_docs') or '').split()   # pages left out of the site aren't checked

LIST_ITEM = re.compile(r'^( *)([-*+]|\d+\.) +\S')   # Python-Markdown doesn't number lists with "1)"
FENCE = re.compile(r'^ *(```|~~~)')
BLOCK_START = re.compile(r'^(#|\||>|<|```|~~~|---|\*\*\*|___)')  # can't be a lazy continuation of a list item
INDENT_STEP = 4


def fix_lists(text: str) -> str:
    """
    Convert github.com (CommonMark) list layout to what Python-Markdown accepts:
      * a list must follow a blank line -- github.com lets one start straight after a paragraph
      * each nesting level must be indented 4 spaces -- github.com accepts 2 or 3
      * an item that follows one containing a blank line must start after a blank line too --
        Python-Markdown splits a page into blocks at blank lines, and an indented block would
        otherwise carry the next item into the previous one
    Item continuation lines and fenced code inside items are shifted with their item.
    """
    out: list[str] = []
    stack: list[list] = []                  # open items: [src marker indent, src content indent, new content indent, blank line inside]
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
                for open_item in stack:
                    open_item[3] = True
            out.append(line)
            continue

        if not line.strip():
            out.append(line)
            prev_blank, prev_item = True, False
            loose = loose or bool(stack)
            for open_item in stack:
                open_item[3] = True
            continue

        indent = len(line) - len(line.lstrip())
        item = LIST_ITEM.match(line)
        if item and not stack and not prev_blank and item.group(2)[0].isdigit() and item.group(2) != '1.':
            item = None                    # inside a paragraph, only "1." starts a numbered list
        if stack and not item and indent == 0 and (prev_blank or BLOCK_START.match(line)):
            stack.clear()                  # unindented text after a blank line, or a heading etc, ends the list

        shift = 0
        if item:
            sibling = closed_blank = False
            while stack and indent < stack[-1][1]:   # left of an open item's content: not its child
                sibling = True
                closed_blank = stack.pop()[3] or closed_blank
            if not prev_blank and ((not prev_item and (not sibling or loose)) or closed_blank):
                out.append('')             # a list starting straight after text, or the next item after one with a blank line
            loose = False
            new_indent = stack[-1][2] if stack else 0
            stack.append([indent, item.end() - 1, new_indent + INDENT_STEP, False])
            line = ' ' * new_indent + line.lstrip()
        elif stack and indent:             # an item's continuation line (indent 0 is a lazy continuation)
            # After a blank line (or starting a new block such as a quote), a line left of a nested item's
            # content belongs to its parent; straight after the item's text it's a lazy continuation of that item
            while (prev_blank or BLOCK_START.match(line.lstrip())) and len(stack) > 1 and indent < stack[-1][1]:
                stack.pop()
            _, src_content, new_content, _ = stack[-1]
            shift = new_content - src_content if indent < new_content else 0   # already deep enough: leave it
            line = ' ' * max(new_content, indent + shift) + line.lstrip()

        if FENCE.match(line):
            fence_shift = shift
        out.append(line)
        prev_blank, prev_item = False, bool(item)
    return '\n'.join(out)


def main() -> None:
    if '--version' in sys.argv:
        print(CONFIG['extra']['docs_version'])
        return
    fix = '--fix' in sys.argv
    bad = []
    for path in sorted(DOCS.rglob('*.md')):
        if any(fnmatch.fnmatch(path.relative_to(DOCS).as_posix(), pattern.strip('/')) for pattern in EXCLUDE):
            continue
        text = path.read_text(encoding='utf-8')
        fixed = fix_lists(text)
        if fixed != text:
            bad.append(path)
            if fix:
                path.write_text(fixed, encoding='utf-8')
    for path in bad:
        print(f'{"fixed" if fix else "needs fixing"}: {path.relative_to(ROOT)}')
    if bad and not fix:
        print('Lists that render differently on the docs site; run with --fix to correct them.')
        sys.exit(1)


if __name__ == '__main__':
    main()
