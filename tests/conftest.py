"""
Shared pytest setup.

Slow tests (long digital-twin simulations, tens of seconds each) are marked @pytest.mark.slow and
skipped by default so the regular suite stays quick. Run them with:

    uv run pytest --runslow                 # whole suite including slow tests
    uv run pytest --runslow -m slow         # only the slow tests

Every test writes its alignment model (sync_points.json) to a temporary directory: the sync manager saves it on every
sync, and the tests' syncs (Az 170/80/260/180) overwrote the developer's data/sync_points.json, so the next driver
start restored 4 sync points that were never taken.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
import control                                                                      # noqa: E402


@pytest.fixture(autouse=True)
def _sync_points_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(control, 'SYNC_POINTS_PATH', tmp_path / 'sync_points.json')


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False,
                     help="also run tests marked slow (long digital-twin simulations)")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: long-running test, skipped unless --runslow is given")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip_slow = pytest.mark.skip(reason="slow test: run with --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
