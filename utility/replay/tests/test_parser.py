import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from replay import KeywordLine, RequestLine, parse_file, parse_line


def test_real_put_line_parses_and_strips_session_keys():
    line = ("2026-08-27T09:03:06.687 INFO 127.0.0.1 -> PUT /api/v1/telescope/0/action "
            "{'Action': 'Polaris:ResetAxes', 'Parameters': ' ', 'ClientID': '8644', "
            "'ClientTransactionID': '1006'}")
    instr = parse_line(line)
    assert isinstance(instr, RequestLine)
    assert instr.method == "PUT"
    assert instr.path == "/api/v1/telescope/0/action"
    assert instr.body == {'Action': 'Polaris:ResetAxes', 'Parameters': ' '}
    assert 'ClientID' not in instr.body
    assert 'ClientTransactionID' not in instr.body


def test_real_get_line_parses_query_and_strips_session_keys():
    line = "2026-08-24T07:17:01.537 INFO 192.168.137.1 -> GET /api/v1/telescope/0/canmoveaxis?ClientID=18351&ClientTransactionID=23&Axis=0"
    instr = parse_line(line)
    assert isinstance(instr, RequestLine)
    assert instr.method == "GET"
    assert instr.path == "/api/v1/telescope/0/canmoveaxis"
    assert instr.query == {'Axis': '0'}
    assert instr.body is None


def test_get_line_with_no_query_string():
    line = "192.168.137.1 -> GET /api/v1/telescope/0/tracking"
    instr = parse_line(line)
    assert instr.method == "GET"
    assert instr.path == "/api/v1/telescope/0/tracking"
    assert instr.query == {}


def test_sleep_keyword_line():
    instr = parse_line("REPLAY SLEEP {\"seconds\": 5}")
    assert instr == KeywordLine("SLEEP", {"seconds": 5})


def test_keyword_line_with_no_timestamp_or_level():
    instr = parse_line('SLEEP {"seconds": 2.5}')
    assert instr == KeywordLine("SLEEP", {"seconds": 2.5})


def test_keyword_line_level_word_is_ignored_whatever_it_is():
    a = parse_line('INFO SLEEP {"seconds": 1}')
    b = parse_line('REPLAY SLEEP {"seconds": 1}')
    c = parse_line('WHATEVER SLEEP {"seconds": 1}')
    assert a == b == c == KeywordLine("SLEEP", {"seconds": 1})


def test_syncguide_pe_keyword_line():
    line = ('REPLAY SYNCGUIDE_PE {"ra_model": [8.0, 12.5, 3.0], "dec_model": [0, 3.0, 1.0], '
            '"exposure_s": 110, "session_min": 120}')
    instr = parse_line(line)
    assert instr.keyword == "SYNCGUIDE_PE"
    assert instr.payload["ra_model"] == [8.0, 12.5, 3.0]
    assert instr.payload["exposure_s"] == 110


def test_pulseguide_pe_keyword_line():
    line = 'PULSEGUIDE_PE {"ra_model": [0,0,0], "dec_model": [0,0,0], "exposure_s": 5, "session_min": 1}'
    instr = parse_line(line)
    assert instr.keyword == "PULSEGUIDE_PE"


def test_wait_settled_keyword_line():
    instr = parse_line('REPLAY WAIT_SETTLED {"timeout_s": 60}')
    assert instr == KeywordLine("WAIT_SETTLED", {"timeout_s": 60})


def test_wait_settled_keyword_line_with_empty_payload():
    instr = parse_line('WAIT_SETTLED {}')
    assert instr == KeywordLine("WAIT_SETTLED", {})


@pytest.mark.parametrize("line", [
    "2026-08-27T09:00:56.880 INFO ==STARTUP== ALPACA BENRO POLARIS DRIVER v2.2.0 Beta 4.3 ===========",
    "2026-08-27T10:24:01.543 INFO PECLOG {'n': 2, 'inhibit': ['TOO_FEW_OBS', 'TOO_FEW_OBS']}",
    "2026-08-27T09:00:57.775 INFO <<- Polaris: BATTERY status changed: 778 {'capacity': '96'}",
    "2026-08-27T09:03:07.695 INFO 127.0.0.1 <- ResetAxes ok",
    "2026-08-24T07:14:34.697 WARNING ->> Heartbeat lag detected:   pulse 5.898s (expected 0.100s)",
    "",
    "   ",
])
def test_irrelevant_lines_are_ignored(line):
    assert parse_line(line) is None


def test_malformed_keyword_payload_raises_with_useful_message():
    with pytest.raises(ValueError, match="SLEEP"):
        parse_line("SLEEP {not valid json}")


def test_malformed_request_body_raises():
    with pytest.raises(ValueError):
        parse_line("127.0.0.1 -> PUT /api/v1/telescope/0/tracking {not: valid, python}")


def test_put_line_with_non_dict_looking_body_is_not_recognised():
    # Real captured PUT bodies always come from Falcon's form-media dict, so this shape can't
    # actually occur -- but confirm it's silently ignored (not a crash) rather than misparsed.
    assert parse_line("127.0.0.1 -> PUT /api/v1/telescope/0/tracking [1, 2, 3]") is None


def test_parse_file_drops_none_lines_and_preserves_order(tmp_path):
    content = (
        "2026-08-27T09:00:56.880 INFO ==STARTUP== banner, ignored\n"
        "REPLAY SLEEP {\"seconds\": 1}\n"
        "\n"
        "127.0.0.1 -> PUT /api/v1/telescope/0/tracking {'Tracking': 'true', 'ClientID': '1', 'ClientTransactionID': '2'}\n"
        "2026-08-27T09:00:57.138 INFO PECLOG {'n': 1}\n"
        "REPLAY SYNCGUIDE_PE {\"ra_model\": [1,0,0], \"dec_model\": [0,0,0], \"exposure_s\": 5, \"session_min\": 1}\n"
    )
    f = tmp_path / "test.log"
    f.write_text(content)

    instructions = parse_file(str(f))
    line_nos = [ln for ln, _ in instructions]
    kinds = [type(instr).__name__ for _, instr in instructions]

    assert line_nos == [2, 4, 6]
    assert kinds == ["KeywordLine", "RequestLine", "KeywordLine"]


def test_parse_file_error_message_includes_path_and_line_number(tmp_path):
    f = tmp_path / "bad.log"
    f.write_text('SLEEP {"seconds": }\n')  # braces balance (matches the keyword regex) but the JSON inside doesn't
    with pytest.raises(ValueError, match=r"bad\.log:1:"):
        parse_file(str(f))
