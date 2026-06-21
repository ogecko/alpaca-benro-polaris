# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# presets.py - Named Preset Manager
# -----------------------------------------------------------------------------
#
# Manages persistent stores of named presets, one JSON file per preset type.
# Currently supports two preset types:
#
#   "loc"  - observation site properties  → data/locations.json
#   "pano" - panorama capture properties  → data/panoramas.json
#
# Triggered via the Config properties:
#   preset_name   - the preset name to act on (e.g. "Sydney Observatory")
#   preset_action - one of:
#                     "save_loc"    "load_loc"    "delete_loc"
#                     "save_pano"   "load_pano"   "delete_pano"
#                   or "" (no-op)
#   loc_list      - pipe-separated list of saved location names (read-only for UI)
#   pano_list     - pipe-separated list of saved panorama names (read-only for UI)
#
# Usage (called from polaris.py make_config_params_live):
#
#   from presets import PresetManager
#   ...
#   elif param == "preset_action":
#       PresetManager.handle_action(Config)
#
# -----------------------------------------------------------------------------

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

# ---------------------------------------------------------------------------
# Hardcoded preset type registry
# ---------------------------------------------------------------------------
# Each entry defines:
#   keys      - Config attribute names that constitute one preset record
#   list_key  - Config attribute name for the pipe-separated name list (UI)
#   file      - JSON file (inside _DATA_DIR) that stores presets of this type
# ---------------------------------------------------------------------------

_PRESET_TYPES: dict[str, dict] = {
    'loc': {
        'name_key': 'location',
        'list_key': 'location_list',
        'keys':     ['site_latitude', 'site_longitude', 'site_elevation', 'site_pressure'],
        'file':     _DATA_DIR / 'locations.json',
    },
    'pano': {
        'name_key': 'pano_name',
        'list_key': 'pano_list',
        'keys':     [
            'cols', 'rows', 'hstep', 'vstep', 'first', 'order',
            'track', 'anchor', 'ref', 'r1', 'r2', 'r3',
            'panel', 'sensor_size', 'panel_overlap',
        ],
        'file':     _DATA_DIR / 'panoramas.json',
    },
}


class PresetManager:
    """Static helpers for persisting named config presets."""

# ── Public entry point ─────────────────────────────────────────────────────────────

    @classmethod
    def handle_action(cls, Config) -> None:
        """
        Inspect Config.preset_action and dispatch to save / load / delete.

        preset_action format: "<verb>_<type>"  e.g. "save_loc", "load_pano"
        preset_name must be set in Config before preset_action is applied.

        Always clears preset_action back to "" and refreshes both list fields
        in Config afterward.
        """
        action_raw = (Config.preset_action or '').strip().lower()
        name       = (Config.preset_name   or '').strip()

        try:
            if not action_raw:
                return  # no-op

            parts = action_raw.split('_', 1)
            if len(parts) != 2:
                logger.warning(f'PresetManager: unrecognised action "{action_raw}", ignoring.')
                return

            verb, type_key = parts

            if type_key not in _PRESET_TYPES:
                logger.warning(f'PresetManager: unknown preset type "{type_key}", ignoring.')
                return

            if verb == 'save':
                cls._save(Config, type_key, name)
            elif verb == 'load':
                cls._load(Config, type_key, name)
            elif verb == 'delete':
                cls._delete(Config, type_key, name)
            else:
                logger.warning(f'PresetManager: unknown verb "{verb}", ignoring.')

        finally:
            # Always reset the action flag and refresh all list fields
            cls.refresh_all_lists(Config)
            Config.apply_changes({'preset_action': ''})

    # ── Actions ─────────────────────────────────────────────────────────────

    @classmethod
    def _save(cls, Config, type_key: str, name: str) -> None:
        """Persist the current values of this type's keys under *name*. On success, writes name_key"""
        if not name:
            logger.warning('PresetManager: cannot save — preset_name is empty.')
            return

        spec = _PRESET_TYPES[type_key]
        data = cls._load_file(spec['file'])
        data[name] = {k: getattr(Config, k) for k in spec['keys']}
        cls._save_file(spec['file'], data)
        Config.apply_changes({spec['name_key']: name})
        logger.info(f'PresetManager: saved {type_key} preset "{name}".')

    @classmethod
    def _load(cls, Config, type_key: str, name: str) -> None:
        """Apply the stored values for *name* to Config. On success, updates name_key"""
        if not name:
            logger.warning('PresetManager: cannot load — preset_name is empty.')
            return

        spec = _PRESET_TYPES[type_key]
        data = cls._load_file(spec['file'])
        if name not in data:
            logger.warning(f'PresetManager: {type_key} preset "{name}" not found.')
            return

        entry: dict[str, Any] = data[name]
        changes = {k: entry[k] for k in spec['keys'] if k in entry}
        Config.apply_changes(changes)
        Config.apply_changes({spec['name_key']: name})
        logger.info(f'PresetManager: loaded {type_key} preset "{name}".')

    @classmethod
    def _delete(cls, Config, type_key: str, name: str) -> None:
        """Remove *name* from the store (no-op if it does not exist). Clears name_key if it matches deleted preset"""
        if not name:
            logger.warning('PresetManager: cannot delete — preset_name is empty.')
            return

        spec = _PRESET_TYPES[type_key]
        data = cls._load_file(spec['file'])
        if name not in data:
            logger.warning(f'PresetManager: {type_key} preset "{name}" not found, nothing deleted.')
            return

        del data[name]
        cls._save_file(spec['file'], data)
        if (getattr(Config, spec['name_key'], '') or '').strip() == name:
            Config.apply_changes({spec['name_key']: ''})
        logger.info(f'PresetManager: deleted {type_key} preset "{name}".')

    # ── List Maintenance ─────────────────────────────────────────────────────────────

    @classmethod
    def refresh_all_lists(cls, Config) -> None:
        """Rebuild all *_list fields in Config from their respective JSON files."""
        for spec in _PRESET_TYPES.values():
            data   = cls._load_file(spec['file'])
            joined = '|'.join(sorted(data.keys()))
            Config.apply_changes({spec['list_key']: joined})

    @classmethod
    def refresh_list(cls, Config, type_key: str) -> None:
        """Rebuild the list field for a single preset type."""
        spec   = _PRESET_TYPES[type_key]
        data   = cls._load_file(spec['file'])
        joined = '|'.join(sorted(data.keys()))
        Config.apply_changes({spec['list_key']: joined})

    # ── File I/O ─────────────────────────────────────────────────────────────

    @classmethod
    def _load_file(cls, path: Path) -> dict:
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f'PresetManager: failed to read {path}: {e}')
        return {}

    @classmethod
    def _save_file(cls, path: Path, data: dict) -> None:
        try:
            os.makedirs(path.parent, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(f'PresetManager: failed to write {path}: {e}')