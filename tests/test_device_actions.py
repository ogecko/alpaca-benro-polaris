"""
Device Actions (PUT /api/v1/telescope/0/action) as clients other than Pilot see them, eg NINA's Device Action.
"""
import asyncio
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "driver"))

import pytest                                                                       # noqa: E402

from config import Config                                                           # noqa: E402


def _install_telescope_action(monkeypatch, action_name, parameters=" "):
    """Run telescope.action's handler without Falcon: the request fields are given, and the response's text is the
    Value the handler passes to PropertyResponse."""
    import exceptions
    import shr
    import telescope

    request = SimpleNamespace(context=SimpleNamespace(), method="PUT")
    response = SimpleNamespace(text=None)
    request_fields = {"Action": action_name, "Parameters": parameters, "ClientID": "1", "ClientTransactionID": "1"}

    async def get_request_field(name, req, *args, **kwargs):
        return request_fields.get(name, kwargs.get("default", "1"))

    async def log_request(*args, **kwargs):
        return None

    async def property_response(value, req, error=None):
        return value

    logger = logging.getLogger("test_device_actions")
    monkeypatch.setattr(telescope, "get_request_field", get_request_field)
    monkeypatch.setattr(telescope, "log_request", log_request)
    monkeypatch.setattr(telescope, "PropertyResponse", property_response)
    monkeypatch.setattr(telescope, "logger", logger)
    monkeypatch.setattr(shr, "get_request_field", get_request_field)
    monkeypatch.setattr(shr, "log_request", log_request)
    monkeypatch.setattr(exceptions, "logger", logger)
    return telescope, request, response


@pytest.mark.parametrize("action_name", ["Polaris:ConfigUpdate", "Polaris:ConfigSave", "Polaris:ConfigRestore"])
def test_config_actions_return_a_json_string(monkeypatch, action_name):
    # ASCOM's Action returns a string: NINA's Device Action failed on the JSON object these used to return
    telescope, request, response = _install_telescope_action(monkeypatch, action_name, '{"pid_Kc": 15}')
    monkeypatch.setattr(Config, "apply_changes", classmethod(lambda cls, params: dict(params)))
    monkeypatch.setattr(Config, "save_pilot_overrides", classmethod(lambda cls: {"pid_Kc": 15}))
    monkeypatch.setattr(Config, "restore_base", classmethod(lambda cls: {"pid_Kc": 15}))
    monkeypatch.setattr(telescope, "polaris", SimpleNamespace(make_config_params_live=lambda changed: None))

    asyncio.run(telescope.action().on_put(request, response, 0))

    assert isinstance(response.text, str)
    assert json.loads(response.text) == {"pid_Kc": 15}
