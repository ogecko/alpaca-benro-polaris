import os
import sys
from unittest.mock import patch

import pytest
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from replay import DriverError, DriverSession


def _resp(json_body, status=200):
    r = requests.Response()
    r.status_code = status
    r.json = lambda: json_body
    return r


def test_get_retries_transient_not_connected_error_then_succeeds():
    session = DriverSession("http://localhost:5555", retries=3, sleep=lambda s: None)
    responses = [
        _resp({"ErrorNumber": 1031, "ErrorMessage": "The device is not connected."}),
        _resp({"ErrorNumber": 0, "ErrorMessage": "", "Value": 12.5}),
    ]
    with patch("replay.requests.get", side_effect=responses):
        assert session.get_property("rightascension") == 12.5


def test_get_gives_up_after_retries_exhausted_on_persistent_transient_error():
    session = DriverSession("http://localhost:5555", retries=2, sleep=lambda s: None)
    always_transient = _resp({"ErrorNumber": 1031, "ErrorMessage": "The device is not connected."})
    with patch("replay.requests.get", return_value=always_transient) as mock_get:
        with pytest.raises(DriverError):
            session.get_property("rightascension")
        assert mock_get.call_count == 2


def test_non_transient_alpaca_error_is_not_retried():
    session = DriverSession("http://localhost:5555", retries=5, sleep=lambda s: None)
    bad_value = _resp({"ErrorNumber": 1025, "ErrorMessage": "InvalidValueException"})
    with patch("replay.requests.get", return_value=bad_value) as mock_get:
        with pytest.raises(DriverError):
            session.get_property("rightascension")
        assert mock_get.call_count == 1


def test_network_exception_is_retried_then_succeeds():
    session = DriverSession("http://localhost:5555", retries=3, sleep=lambda s: None)
    ok = _resp({"ErrorNumber": 0, "ErrorMessage": "", "Value": True})
    with patch("replay.requests.get", side_effect=[requests.ConnectionError("boom"), ok]):
        assert session.get_property("connected") is True


def test_each_retry_attempt_mints_a_fresh_transaction_id():
    session = DriverSession("http://localhost:5555", retries=3, sleep=lambda s: None)
    responses = [
        _resp({"ErrorNumber": 1031, "ErrorMessage": "not connected"}),
        _resp({"ErrorNumber": 0, "ErrorMessage": "", "Value": 1}),
    ]
    seen_txn_ids = []

    def fake_get(url, params, timeout):
        seen_txn_ids.append(params["ClientTransactionID"])
        return responses[len(seen_txn_ids) - 1]

    with patch("replay.requests.get", side_effect=fake_get):
        session.get_property("connected")
    assert seen_txn_ids[0] != seen_txn_ids[1]
