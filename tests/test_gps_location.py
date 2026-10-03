import sys
from pathlib import Path
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "driver"))

import gps_location


def test_try_gpsd_uses_supported_datetime_keyword(monkeypatch):
    tpv = {"mode": 3, "lat": 51.5, "lon": -0.12, "altMSL": 35.0}

    class GPSDClient:
        def __init__(self, host, port):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def dict_stream(self, *, convert_datetime=True, filter=None):
            assert convert_datetime is True
            assert filter == ["TPV"]
            return iter([tpv])

    gpsdclient = ModuleType("gpsdclient")
    gpsdclient.GPSDClient = GPSDClient
    monkeypatch.setitem(sys.modules, "gpsdclient", gpsdclient)

    assert gps_location._try_gpsd(timeout=2.0) == (51.5, -0.12, 35.0)