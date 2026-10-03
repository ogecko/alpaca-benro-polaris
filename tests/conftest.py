"""
Shared pytest setup.

Slow tests (long digital-twin simulations, tens of seconds each) are marked @pytest.mark.slow and
skipped by default so the regular suite stays quick. Run them with:

    uv run pytest --runslow                 # whole suite including slow tests
    uv run pytest --runslow -m slow         # only the slow tests
"""
import pytest


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
