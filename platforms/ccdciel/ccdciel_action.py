import json
import sys
import requests
import re

host = "192.168.50.54"
port = "5555" 

def alpaca_action(action_name, params_dict=None, device_number=0, client_id=100):
    """
    Execute an Alpaca Action command.
    params_dict is optional.
    """
    url = (
        f"http://{host}:{port}"
        f"/api/v1/telescope/{device_number}/action"
    )

    # Alpaca Action.Parameters must be a string
    parameters = "" if params_dict is None else json.dumps(params_dict)
    payload = {
        "Action": action_name,
        "Parameters": parameters,
        "ClientID": client_id,
        "ClientTransactionID": 1,
    }

    response = requests.put(url, data=payload, timeout=10)
    response.raise_for_status()
    result = response.json()

    if result.get("ErrorNumber", 0) != 0:
        raise RuntimeError(
            f"Alpaca error {result['ErrorNumber']}: "
            f"{result.get('ErrorMessage')}"
        )

    return result.get("Value")


def parse_ccdciel_params(argv):
    """
    Robust CCDciel parameter parser.
    CCDciel Script Arguments: Polaris:PanoSlew, {"panel":13, "id": 4 }
    Python Script Arguments:  ['C:\\Users\\Nina\\AppData\\Local\\ccdciel\\tmpscript', 'Polaris:PanoSlew,', '{panel:13,', 'id:', '4', '}']

    Handles:
    - argv splitting issues
    - missing quotes around keys
    - trailing commas
    - partial JSON like {panel:13}
    - empty or missing params

    Returns:
        dict | None
    """

    # 1. Join everything after action name
    raw = " ".join(argv[2:]).strip() if len(argv) > 2 else ""
    if not raw:
        return None
    s = raw.strip()

    # 2. Remove stray commas before closing braces/brackets
    s = re.sub(r",\s*([}\]])", r"\1", s)

    # 3. If already valid JSON, parse directly
    try:
        return json.loads(s)
    except Exception:
        pass

    # 4. Fix unquoted keys: {panel:13, mode:2}
    s = re.sub(
        r'([{\s,])([A-Za-z_][A-Za-z0-9_]*)\s*:',
        r'\1"\2":',
        s
    )

    # 5. Fix single quotes (if CCDciel ever produces them)
    s = s.replace("'", '"')

    # 6. Final attempt
    try:
        return json.loads(s)
    except Exception as e:
        raise ValueError(
            f"Could not parse CCDciel params: {raw} -> {s}"
        ) from e
    

def main():
    print(f"{sys.argv!r}")

    if len(sys.argv) < 2:
        print("Usage: <action_name> [params]")
        return

    action_name = sys.argv[1]
    params_dict = parse_ccdciel_params(sys.argv)

    result = alpaca_action(action_name, params_dict)
    print("Result:", result)

    try:
        result = alpaca_action(action_name, params_dict)
        print("Result:", result)

    except Exception as e:
        print("Error:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()