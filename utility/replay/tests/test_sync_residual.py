import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from replay import KeywordLine, RequestLine, _dms_to_deg, _pair_sync_residual, parse_file, run

# Real captured lines, verbatim from logs/logs/alpaca.jdm_Beta3.1_08_02.log
REAL_PAIRED_BLOCK = [
    "2026-08-02T08:08:52.816 INFO 169.254.176.36 <- True\n",
    "2026-08-02T08:08:52.821 INFO 169.254.176.36 -> PUT /api/v1/telescope/0/synctocoordinates "
    "{'RightAscension': '10.754335604246782', 'Declination': '-60.03948766881228', 'ClientID': '16398', 'ClientTransactionID': '12986'}\n",
    "2026-08-02T08:08:52.822 INFO ->> Polaris: SYNC Observed   Ra 10h45m15.61s Dec -060d02'22.16\" Az +216d45'49.58\" Alt +042d00'25.05\" (Multi-Point Alignment)\n",
    "2026-08-02T08:08:52.822 INFO ->> Polaris: SYNC GUIDING    Ra +000d00'00.93\", Dec -000d00'04.16\" Residuals\n",
]


def test_dms_to_deg():
    assert _dms_to_deg('+', '0', '0', '0.93') == pytest.approx(0.93 / 3600)
    assert _dms_to_deg('-', '0', '0', '4.16') == pytest.approx(-4.16 / 3600)
    assert _dms_to_deg('+', '1', '30', '0') == pytest.approx(1.5)


def test_pair_sync_residual_finds_real_captured_pattern():
    result = _pair_sync_residual(REAL_PAIRED_BLOCK, 1)  # PUT line is index 1
    assert result is not None
    ra_resid, dec_resid = result
    assert ra_resid == pytest.approx(0.93 / 3600)
    assert dec_resid == pytest.approx(-4.16 / 3600)


def test_pair_sync_residual_returns_none_when_not_present():
    lines = [
        "IP -> PUT /api/v1/telescope/0/synctocoordinates {'RightAscension': '10.0', 'Declination': '-60.0'}\n",
        "INFO some other unrelated line\n",
        "INFO ->> Polaris: SYNC Observed   Ra 10h00m00.00s Dec -060d00'00.00\" (Single-Point Alignment)\n",
    ]
    assert _pair_sync_residual(lines, 0) is None


def test_parse_file_converts_paired_synctocoordinates_to_sync_residual(tmp_path):
    f = tmp_path / "real_capture.log"
    f.write_text("".join(REAL_PAIRED_BLOCK))
    instructions = parse_file(str(f))
    # Only the paired PUT line becomes an instruction (line 2); the "<- True" and the two
    # ->> Polaris info lines are not recognised shapes, so they're dropped as usual.
    assert len(instructions) == 1
    line_no, instr = instructions[0]
    assert line_no == 2
    assert isinstance(instr, KeywordLine)
    assert instr.keyword == "SYNC_RESIDUAL"
    assert instr.payload["ra_resid_deg"] == pytest.approx(0.93 / 3600)
    assert instr.payload["dec_resid_deg"] == pytest.approx(-4.16 / 3600)


def test_parse_file_leaves_unpaired_synctocoordinates_as_a_plain_request_line(tmp_path):
    f = tmp_path / "unpaired.log"
    f.write_text(
        "IP -> PUT /api/v1/telescope/0/synctocoordinates "
        "{'RightAscension': '10.0', 'Declination': '-60.0', 'ClientID': '1', 'ClientTransactionID': '2'}\n"
        "INFO ->> Polaris: SYNC Observed   Ra 10h00m00.00s Dec -060d00'00.00\" Az +100d00'00.00\" "
        "Alt +040d00'00.00\" (Single-Point Alignment)\n"
    )
    instructions = parse_file(str(f))
    assert len(instructions) == 1
    line_no, instr = instructions[0]
    assert isinstance(instr, RequestLine)
    assert instr.path == "/api/v1/telescope/0/synctocoordinates"


def test_sync_residual_keyword_line_can_be_hand_written():
    from replay import parse_line
    instr = parse_line('REPLAY SYNC_RESIDUAL {"ra_resid_deg": 0.001, "dec_resid_deg": -0.002}')
    assert instr == KeywordLine("SYNC_RESIDUAL", {"ra_resid_deg": 0.001, "dec_resid_deg": -0.002})


# ── run() integration ────────────────────────────────────────────────────────

class RecordingSession:
    def __init__(self, ra_h=10.0, dec_d=-60.0):
        self._ra_h = ra_h
        self._dec_d = dec_d
        self.puts = []

    def get_property(self, name):
        return {"rightascension": self._ra_h, "declination": self._dec_d}[name]

    def put_property(self, name, body):
        self.puts.append((name, body))

    def put(self, path, body):
        self.puts.append((path, body))

    def get(self, path, query=None):
        return None


def test_run_applies_sync_residual_against_current_position():
    instructions = [(1, KeywordLine("SYNC_RESIDUAL", {"ra_resid_deg": 0.001, "dec_resid_deg": -0.002}))]
    session = RecordingSession(ra_h=10.0, dec_d=-60.0)
    run(instructions, session, log=lambda *a: None)
    name, body = session.puts[0]
    assert name == "synctocoordinates"
    assert body["RightAscension"] == pytest.approx(10.0 + 0.001 / 15.0)
    assert body["Declination"] == pytest.approx(-60.0 - 0.002)


def test_run_replays_real_captured_pair_end_to_end(tmp_path):
    f = tmp_path / "real_capture.log"
    f.write_text("".join(REAL_PAIRED_BLOCK))
    instructions = parse_file(str(f))
    session = RecordingSession(ra_h=10.754335604246782, dec_d=-60.03948766881228)
    run(instructions, session, log=lambda *a: None)
    name, body = session.puts[0]
    assert name == "synctocoordinates"
    # Applied against the (fake) *current* position, not the raw captured absolute value --
    # here they happen to be the same number, so this also confirms the offset math directly.
    assert body["RightAscension"] == pytest.approx(10.754335604246782 + (0.93 / 3600) / 15.0)
    assert body["Declination"] == pytest.approx(-60.03948766881228 - 4.16 / 3600)
