# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# locations.py - Named Observation Site Manager
# -----------------------------------------------------------------------------
#
# Manages a persistent store of named observation sites in locations.json.
# Each entry captures the four site properties (latitude, longitude, elevation,
# pressure) keyed by a human-readable location name.
#
# Triggered via the Config properties:
#   location        - the site name (e.g. "Sydney Observatory, Australia")
#   location_action - one of "save", "delete", "load", or "" (no-op)
#   location_list   - pipe-separated list of saved names (read-only for UI)
#
# Usage (called from polaris.py make_config_params_live):
#
#   from locations import LocationManager
#   ...
#   elif param == "location_action":
#       LocationManager.handle_action(Config)
#
# -----------------------------------------------------------------------------

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Location of the persistent store, parallel to config.pilot.json
_DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
LOCATIONS_PATH = _DATA_DIR / 'locations.json'

# The Config keys that constitute a "location"
LOCATION_KEYS = ['site_latitude', 'site_longitude', 'site_elevation', 'site_pressure']


class LocationManager:
    """Static helpers for persisting named observation sites."""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    @classmethod
    def handle_action(cls, Config) -> None:
        """
        Inspect Config.location_action and dispatch to save / delete / load.
        Always clears location_action back to "" and refreshes location_list
        in Config afterward.
        """
        action = (Config.location_action or '').strip().lower()
        name   = (Config.location or '').strip()

        try:
            if action == 'save':
                cls._save(Config, name)
            elif action == 'delete':
                cls._delete(Config, name)
            elif action == 'load':
                cls._load(Config, name)
            elif action == '':
                pass  # location name changed with no action — nothing to do
            else:
                logger.warning(f'LocationManager: unknown action "{action}", ignoring.')
        finally:
            # Always reset the action flag and refresh the list
            cls.refresh_list(Config)
            Config.apply_changes({'location_action': ''})

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @classmethod
    def _save(cls, Config, name: str) -> None:
        """Persist the current site properties under *name*."""
        if not name:
            logger.warning('LocationManager: cannot save — location name is empty.')
            return

        data = cls._load_file()
        data[name] = {k: getattr(Config, k) for k in LOCATION_KEYS}
        cls._save_file(data)
        logger.info(f'LocationManager: saved "{name}"')

    @classmethod
    def _delete(cls, Config, name: str) -> None:
        """Remove *name* from the store (no-op if it does not exist)."""
        if not name:
            logger.warning('LocationManager: cannot delete — location name is empty.')
            return

        data = cls._load_file()
        if name in data:
            del data[name]
            cls._save_file(data)
            logger.info(f'LocationManager: deleted "{name}".')
        else:
            logger.warning(f'LocationManager: "{name}" not found, nothing deleted.')

    @classmethod
    def _load(cls, Config, name: str) -> None:
        """Apply the stored site properties for *name* to Config. WARNING not that it doesnt update polaris properties!"""
        if not name:
            logger.warning('LocationManager: cannot load — location name is empty.')
            return

        data = cls._load_file()
        if name not in data:
            logger.warning(f'LocationManager: "{name}" not found in locations store.')
            return

        entry: dict[str, Any] = data[name]
        changes = {k: entry[k] for k in LOCATION_KEYS if k in entry}
        Config.apply_changes(changes)
        logger.info(f'LocationManager: loaded "{name}"')

    # ------------------------------------------------------------------
    # location_list maintenance
    # ------------------------------------------------------------------

    @classmethod
    def refresh_list(cls, Config) -> None:
        """
        Rebuild Config.location_list as a pipe-separated string of all
        saved location names, sorted alphabetically.
        """
        data = cls._load_file()
        joined = '|'.join(sorted(data.keys()))
        Config.apply_changes({'location_list': joined})

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    @classmethod
    def _load_file(cls) -> dict:
        if LOCATIONS_PATH.exists():
            try:
                with open(LOCATIONS_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f'LocationManager: failed to read {LOCATIONS_PATH}: {e}')
        return {}

    @classmethod
    def _save_file(cls, data: dict) -> None:
        try:
            os.makedirs(LOCATIONS_PATH.parent, exist_ok=True)
            with open(LOCATIONS_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(f'LocationManager: failed to write {LOCATIONS_PATH}: {e}')