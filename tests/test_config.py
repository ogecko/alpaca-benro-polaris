import sys, os, json, shutil
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import pytest
from config import Config

DRIVER_DIR = Path(__file__).resolve().parent      # Get the path to the current script (config.py)
CONFIG_DIR = DRIVER_DIR.parent / 'driver'         # Default config directory: ../driver 

CONFIG_TOML_PATH = CONFIG_DIR / 'config.toml'
CONFIG_TEMP_PATH = CONFIG_DIR / 'config.temp.json'

@pytest.fixture
def config_fixture(tmp_path):
    # Setup dummy config.toml and pilot.toml
    tomlpath = tmp_path / 'config.toml'
    tomlpath.write_text("""
    [network]
    ip = "192.168.1.10"
    port = 8080
    """)
    pilotpath = tmp_path / 'config.temp.json'
    pilotpath.write_text("""
    {
    "port": 9000
    }""")
    yield Config, tomlpath, pilotpath


def test_load_and_inject(config_fixture):
    Config, tomlpath, pilotpath = config_fixture
    Config.load(tomlpath, pilotpath)
    assert Config.ip == "192.168.1.10"
    assert Config.port == 9000
    assert Config.get("ip") == "192.168.1.10"

def test_apply_changes_and_diff(config_fixture):
    Config, tomlpath, pilotpath = config_fixture
    Config.load(tomlpath, pilotpath)
    Config.apply_changes({"ip": "10.0.0.42"})
    assert Config.ip == "10.0.0.42"
    assert Config.diff() == {"ip": "10.0.0.42","port": 9000}

def test_save_and_restore(config_fixture):
    Config, tomlpath, pilotpath = config_fixture
    Config.load(tomlpath, pilotpath)
    Config.apply_changes({"port": 1000})
    Config.save_pilot_overrides(pilotpath)
    with open(pilotpath) as f:
        pilot = json.load(f)
    assert pilot == {"port": 1000}
    Config.restore_base(tomlpath, pilotpath)
    assert Config.port == 8080

def test_as_dict(config_fixture):
    Config, tomlpath, pilotpath = config_fixture
    Config.load(tomlpath, pilotpath)
    d = Config.as_dict()
    assert isinstance(d, dict)
    assert d["ip"] == "192.168.1.10"
    assert d["port"] == 9000

def test_apply_nonexistant_key(config_fixture):
    Config, tomlpath, pilotpath = config_fixture
    Config.load(tomlpath, pilotpath)
    applied = Config.apply_changes({"port":20, "junk": "bad data"})
    assert applied == {"port": 20}
    assert "junk" not in Config._current

def test_apply_badtype_key(config_fixture):
    Config, tomlpath, pilotpath = config_fixture
    Config.load(tomlpath, pilotpath)
    applied = Config.apply_changes({"port": "bad data"})
    assert applied == {}
    assert Config.port == 9000

