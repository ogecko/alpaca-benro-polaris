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
WS_URL = f"wss://{HOST}:{WS_PORT}/ws"

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def _dedupe_key(topic, data):
    if topic == "pid":
        return json.dumps([data.get("θ_sp"), data.get("θ_pv"), data.get("ω_op")])
    if topic == "kf":
        return json.dumps([data.get("θ_meas"), data.get("θ_state"), data.get("K_gain")])
    return json.dumps(data)


async def _capture_async(duration_s, topics=("pid", "kf")):
    records = []
    seen = set()
    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline:
        try:
            async with websockets.connect(WS_URL, ssl=_ssl_ctx, open_timeout=10) as ws:
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
        except (OSError, websockets.exceptions.WebSocketException):
            await asyncio.sleep(0.5)
            continue
    return records


def capture(duration_s, topics=("pid", "kf")):
    """Synchronous entry point -- capture telemetry for duration_s seconds,
    deduplicated, reconnecting transparently on drops."""
    return asyncio.run(_capture_async(duration_s, topics))
