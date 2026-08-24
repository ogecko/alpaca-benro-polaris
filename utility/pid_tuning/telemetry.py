"""
Capture live 'pid' + 'kf' telemetry from the Alpaca Pilot WebSocket for a fixed
duration, deduplicating the backlog-replay that happens on every (re)subscribe
(see docs/control.md section 2, and app_socket.py's PublishLogTopic.get_backlog).

Records are returned as plain dicts: {"topic": "pid"|"kf", "t": <local wall
clock time.time() when received>, **payload["data"]}.
"""
import asyncio
import json
import ssl
import time

import websockets

HOST = "localhost"
WS_PORT = 5556

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def _ws_url():
    """wss:// or ws:// depending on the driver's current enable_https setting --
    this has been observed to change between driver restarts within a single
    session, so don't hardcode the scheme."""
    try:
        import alpaca_client as ac
        https = ac.config_fetch(["enable_https"])["enable_https"]
    except Exception:
        https = True  # driver default
    scheme = "wss" if https else "ws"
    return f"{scheme}://{HOST}:{WS_PORT}/ws"


def _dedupe_key(topic, data):
    if topic == "pid":
        return json.dumps([data.get("θ_sp"), data.get("θ_pv"), data.get("ω_op")])
    if topic == "kf":
        return json.dumps([data.get("θ_meas"), data.get("θ_state"), data.get("K_gain")])
    return json.dumps(data)


async def _capture_async(duration_s, topics=("pid", "kf")):
    records = []
    seen = set()
    url = _ws_url()
    ssl_arg = _ssl_ctx if url.startswith("wss:") else None
    deadline = time.monotonic() + duration_s
    consecutive_failures = 0
    while time.monotonic() < deadline:
        try:
            async with websockets.connect(url, ssl=ssl_arg, open_timeout=10) as ws:
                for topic in topics:
                    await ws.send(json.dumps({"type": "subscribe", "topic": topic}))
                last_ping = time.monotonic()
                while time.monotonic() < deadline:
                    if time.monotonic() - last_ping > 3.0:
                        await ws.send(json.dumps({"type": "ping"}))
                        last_ping = time.monotonic()
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue
                    msg = json.loads(raw)
                    data = msg.get("data")
                    topic = msg.get("topic")
                    if not isinstance(data, dict) or topic not in topics:
                        continue
                    key = (topic, _dedupe_key(topic, data))
                    if key in seen:
                        continue
                    seen.add(key)
                    records.append({"topic": topic, "t": time.time(), **data})
        except (OSError, websockets.exceptions.WebSocketException) as ex:
            consecutive_failures += 1
            if consecutive_failures in (1, 5) or consecutive_failures % 20 == 0:
                import sys
                print(f"telemetry.capture: connection to {url} failing ({ex!r}), "
                      f"attempt {consecutive_failures}", file=sys.stderr)
            await asyncio.sleep(0.5)
            continue
        else:
            consecutive_failures = 0
    return records


def capture(duration_s, topics=("pid", "kf")):
    """Synchronous entry point -- capture telemetry for duration_s seconds,
    deduplicated, reconnecting transparently on drops."""
    return asyncio.run(_capture_async(duration_s, topics))
