"""Stub entry points so `uv run driver` launches driver/main.py and `uv run docs` the docs preview."""
import os
import sys
import runpy
from pathlib import Path

def main():
    project_root = Path(__file__).resolve().parents[2]
    driver_dir = project_root / "driver"
    os.chdir(driver_dir)                 # match cwd of running `python main.py` from inside driver/
    sys.path.insert(0, str(driver_dir))  # let sibling imports (e.g. `import exceptions`) resolve
    runpy.run_path(str(driver_dir / "main.py"), run_name="__main__")

def docs():
    """`uv run docs` stages the docs and runs the live Zensical preview (utility/docs/prepare.py --serve)."""
    project_root = Path(__file__).resolve().parents[2]
    os.chdir(project_root)
    sys.argv = [sys.argv[0], *(sys.argv[1:] or ["--serve"])]
    runpy.run_path(str(project_root / "utility" / "docs" / "prepare.py"), run_name="__main__")
