import os, toml, json
from typing import Dict, Any
from pathlib import Path

DRIVER_DIR = Path(__file__).resolve().parent      # Get the path to the current script (config.py)
CONFIG_DIR = DRIVER_DIR.parent / 'driver'         # Default config directory: ../driver 

CONFIG_TOML_PATH = CONFIG_DIR / 'config.toml'
CONFIG_TEMP_PATH = CONFIG_DIR / 'config.temp.json'

class Config:
    _base: Dict[str, Any] = {}
    _current: Dict[str, Any] = {}

    @classmethod
    def load(cls, tomlpath=CONFIG_TOML_PATH, pilotpath=CONFIG_TEMP_PATH):
        """Load config.toml and apply pilot overrides from config.temp.json if present."""
        raw = toml.load(tomlpath)
        cls._base = cls._flatten(raw)
        cls._current = dict(cls._base)  # Shallow copy
        if os.path.exists(pilotpath):
            with open(pilotpath, 'r') as f:
                overrides = json.load(f)
            cls._current.update(overrides)
        cls._inject_attributes()

    @classmethod
    def _flatten(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Convert nested TOML structure into a flat dictionary of key-value pairs."""
        flat = {}
        for key, value in raw.items():
            if isinstance(value, dict):
                flat.update(value)
            else:
                flat[key] = value
        return flat

    @classmethod
    def _inject_attributes(cls):
        """Expose all keys from current config as class-level attributes for direct access."""
        for key, value in cls._current.items():
            setattr(cls, key, value)

    @classmethod
    def apply_changes(cls, changes: dict) -> dict:
        """
        Apply in-memory changes to the current config, validating keys and types.
        Returns a dict of successfully applied changes.
        """
        applied = {}
        for key, new_value in changes.items():
            if key not in cls._current:
                continue
            expected_type = type(cls._current[key])
            try:
                coerced = expected_type(new_value)
            except (ValueError, TypeError):
                continue
            cls._current[key] = coerced
            setattr(cls, key, coerced)
            applied[key] = coerced
        return applied

    @classmethod
    def restore_base(cls, tomlpath=CONFIG_TOML_PATH, pilotpath=CONFIG_TEMP_PATH):
        """Delete pilot override file and reload config from config.toml only."""
        if os.path.exists(pilotpath):
            os.remove(pilotpath)
        cls.load(tomlpath, pilotpath)
        return cls.as_dict()

    @classmethod
    def save_pilot_overrides(cls,pilotpath=CONFIG_TEMP_PATH):
        """Save all changes from current config that differ from config.toml into config.temp.json."""
        changes = cls.diff()
        with open(pilotpath, 'w') as f:
            json.dump(changes, f, indent=2)
        return changes

    @classmethod
    def diff(cls) -> Dict[str, Any]:
        """Return a dictionary of keys whose values differ from the original config.toml."""
        return {
            key: val
            for key, val in cls._current.items()
            if cls._base.get(key) != val
        }

    @classmethod
    def get(cls, key: str) -> Any:
        """Retrieve the current value of a config key."""
        return cls._current.get(key)

    @classmethod
    def as_dict(cls) -> Dict[str, Any]:
        """Return the entire current config as a flat dictionary."""
        return dict(cls._current)
