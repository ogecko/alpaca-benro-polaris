"""Stub entry point so `uv run driver` launches driver/main.py directly."""
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