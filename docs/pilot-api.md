# Pilot API Reference
[Web Server](#web-server) · [HTTPS](#https) · [REST Proxy](#rest-proxy) · [WebSocket](#websocket) · [Live Telemetry](#live-telemetry)

Alongside its ASCOM Alpaca devices (see the [Alpaca API Reference](./alpaca-api.md)), the Alpaca Driver runs the services that Alpaca Pilot uses: a web server for the app itself, a proxy to the Alpaca REST API, and a WebSocket for live data. These are specific to the Alpaca Driver, not part of the ASCOM Alpaca standard. This page is for anyone who wants to script the driver, or build their own tools around it.

## Web Server

The web server serves the Alpaca Pilot app on port `80` (the `alpaca_pilot_http_port` setting), or on port `443` when HTTPS is enabled (`alpaca_pilot_https_port`). It is advertised on the local network over mDNS as `ap.local` (the `mdns_name` setting); see [Launching Alpaca Pilot](./pilot.md#launching-alpaca-pilot) for the other ways to reach it.

| Path | Purpose |
|---|---|
| `/` | The Alpaca Pilot app |
| `/version` | The driver's version and state, as JSON: `driver` (the driver version), `boot` (changes every time the driver restarts), `spa` (changes when Alpaca Pilot is rebuilt) and `https` (whether HTTPS is enabled). Alpaca Pilot uses it to notice a restart or an update. |
| `/alpaca_pilot_ca.crt` | Downloads the certificate to install so browsers trust the driver's HTTPS (see [HTTPS](#https)) |
| `/proxy/...` | Forwards requests to the Alpaca REST API (see [REST Proxy](#rest-proxy)) |
| `/proxy/ws` | Forwards a WebSocket to the driver's WebSocket service (see [WebSocket](#websocket)) |

The web server also listens on the other port and redirects to the active one: with HTTPS enabled, plain HTTP requests are redirected to HTTPS, and with it disabled, HTTPS requests are redirected to HTTP. WebSocket connections can't follow a redirect, so connect to the active port directly.

## HTTPS

With **HTTPS** enabled in Alpaca Pilot (the `enable_https` setting), the web server and the WebSocket use HTTPS and secure WebSockets (`wss://`). The driver creates its own certificate authority and certificate, stored in the `data` folder. Browsers only trust them after you install the authority's certificate from `/alpaca_pilot_ca.crt`, as described in [Using HTTPS](./initial-setup.md#using-https). HTTPS lets phone browsers use location services, for example to set your observing site.

The Alpaca REST API on port `5555` has its own setting, `enable_rest_https`. If you turn it on, applications such as NINA must also be set to use HTTPS for Alpaca discovery.

## REST Proxy

Requests to `/proxy/<path>` on the web server are forwarded to the Alpaca REST API at `<path>`. GET and PUT are supported. This lets a browser reach the REST API through Alpaca Pilot's own address, so it never needs the REST API's separate port, and avoids cross-origin and mixed HTTP/HTTPS problems. The proxy passes the caller's IP address to the REST API in the `X-Forwarded-For` header, and returns `502 Bad Gateway` if the REST API can't be reached.

For example, these two requests are the same:

```
curl "http://ap.local/proxy/api/v1/telescope/0/tracking?ClientID=1&ClientTransactionID=1"
curl "http://ap.local:5555/api/v1/telescope/0/tracking?ClientID=1&ClientTransactionID=1"
```

## WebSocket

The driver's WebSocket service sends Alpaca Pilot its live data. Connect to it either:

* **through the web server's proxy**, at `ws://ap.local/proxy/ws` (`wss://` with HTTPS), as Alpaca Pilot does, or
* **directly**, at `ws://<driver address>:5556/ws` (the `alpaca_socket_port` setting; `wss://` with HTTPS).

Messages in both directions are JSON:

| Message | Meaning |
|---|---|
| `{"type": "subscribe", "topic": "pid"}` | Start receiving a topic's messages |
| `{"type": "unsubscribe", "topic": "pid"}` | Stop receiving a topic's messages |
| `{"type": "ping"}` | Keep the connection open; the driver replies `{"type": "pong"}`. Send one at least every 10 seconds, or the driver closes the connection. |

The topics are:

| Topic | Contents |
|---|---|
| `status` | Mount, alignment and PEC state |
| `pid` | PID controller terms for each motor (`ω_kp`, `ω_ki`, `ω_kd`, `ω_ff`, `ω_pec`, `ω_op`, each an array for M1, M2 and M3) |
| `kf` | Kalman filter estimates |
| `log` | The driver's log messages |
| `sm` | Sync and alignment events, for Alpaca Pilot's Alignment page |
| `cm` | The motor speed calibration table, for the Calibration page |
| `cfg` | Changes to the driver's settings |

## Live Telemetry

This minimal Python client subscribes to the `pid` topic and prints each message, using only the standard library:

```python
import socket, ssl, base64, os, struct, json, sys, time

HOST, PORT, PATH = "localhost", 5556, "/ws"
USE_TLS = False          # True when HTTPS is enabled in Alpaca Pilot (the socket then uses wss://)

def connect():
    sock = socket.create_connection((HOST, PORT), timeout=10)
    if USE_TLS:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        sock = ctx.wrap_socket(sock, server_hostname=HOST)
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall((f"GET {PATH} HTTP/1.1\r\nHost: {HOST}:{PORT}\r\n"
                  f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                  f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    resp = b""
    while b"\r\n\r\n" not in resp: resp += sock.recv(4096)
    return sock

def send_text(sock, msg):
    payload = msg.encode(); mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    n = len(payload)
    hdr = struct.pack("!BB", 0x81, 0x80 | n) if n < 126 else struct.pack("!BBH", 0x81, 0x80|126, n)
    sock.sendall(hdr + mask + masked)

def recv_frames(buf):
    frames = []
    while len(buf) >= 2:
        b0, b1 = buf[0], buf[1]; length = b1 & 0x7F; idx = 2
        if length == 126:
            if len(buf) < 4: return frames
            length = struct.unpack("!H", buf[2:4])[0]; idx = 4
        if len(buf) < idx + length: return frames
        payload = bytes(buf[idx:idx+length]); del buf[:idx+length]
        frames.append((b0 & 0x0F, payload))
    return frames

sock = connect()
send_text(sock, json.dumps({"type": "subscribe", "topic": "pid"}))
sock.settimeout(0.5)
buf = bytearray(); last_ping = time.time()
while True:
    if time.time() - last_ping > 3.0:
        send_text(sock, json.dumps({"type": "ping"})); last_ping = time.time()
    try: buf.extend(sock.recv(65536))
    except socket.timeout: pass
    for opcode, payload in recv_frames(buf):
        if opcode == 0x1:
            msg = json.loads(payload)
            if isinstance(msg.get("data"), dict) and "ω_op" in msg["data"]:
                print(msg["data"])  # ω_kp, ω_ki, ω_kd, ω_ff, ω_pec, ω_op — arrays of 3 (M1/M2/M3)
```
