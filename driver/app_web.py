# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# app_web.py - Alpaca Pilot Web Application module
# -----------------------------------------------------------------------------
import os
import mimetypes
import aiofiles
import asyncio
import aiohttp
import uvicorn
import socket
import psutil
from falcon import asgi, HTTP_200, HTTP_301, WebSocketDisconnected
from config import Config
from pathlib import Path
from shr import LifecycleController, LifecycleEvent, DeviceMetadata, check_port_bindable, describe_bind_error
import datetime
import ipaddress
import hashlib
import time

SCRIPT_DIR = Path(__file__).resolve().parent            # Get the path to the current script
QUASAR_DIST = SCRIPT_DIR.parent / 'pilot' / 'dist' / 'spa'
DATA_DIR    = SCRIPT_DIR.parent / 'data'                # ../data relative to main.py location

TLS_CERT_PATH = DATA_DIR / 'alpaca_pilot.crt'      # server cert + CA chain (for uvicorn)
TLS_KEY_PATH  = DATA_DIR / 'alpaca_pilot.key'      # server private key
CA_CERT_PATH  = DATA_DIR / 'alpaca_pilot_ca.crt'   # CA cert only (for trust store install)
CA_KEY_PATH   = DATA_DIR / 'alpaca_pilot_ca.key'   # CA private key


# ── Low-level x509 helpers ─────────────────────────────────────────────────────────────
def _new_rsa_key():
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    return rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
 
 
def _make_name(common_name: str):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
 
 
def _build_cert(*, subject, issuer, public_key, signing_key, days: int, extensions: list):
    """
    Build and sign an x509 certificate.
    Args:
        subject:     x509.Name for the subject
        issuer:      x509.Name for the issuer (same as subject for self-signed CA)
        public_key:  Public key to embed in the cert
        signing_key: Private key used to sign (CA key for server cert, own key for CA)
        days:        Validity period in days from now
        extensions:  List of (extension_object, critical: bool) tuples
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
 
    now     = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=days))
    )
    for ext, critical in extensions:
        builder = builder.add_extension(ext, critical=critical)
    return builder.sign(signing_key, hashes.SHA256(), default_backend())
 
 
def _pem_key(key) -> bytes:
    from cryptography.hazmat.primitives import serialization
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ) 
 
def _pem_cert(cert) -> bytes:
    from cryptography.hazmat.primitives import serialization
    return cert.public_bytes(serialization.Encoding.PEM)

def _chmod(path: Path, mode: int):
    """Best-effort permission set — silently ignored on Windows."""
    try:
        path.chmod(mode)
    except Exception:
        pass


# ── SAN / network helpers ─────────────────────────────────────────────────────────────

def _get_local_ips() -> list:
    """
    Enumerate this host's real IPv4 addresses across all network interfaces.

    Deliberately does NOT use socket.getaddrinfo(socket.gethostname()) -- under
    Docker (even with --network host) the container's own /etc/hosts maps its
    hostname to a 127.0.1.1-style loopback address, so getaddrinfo returns only
    that loopback IP and every real LAN address silently gets left out of the
    cert's SAN. Enumerate interfaces directly instead, mirroring the approach
    discovery_mdns.pick_lan_ipv4() already uses successfully for the same
    Docker/WSL2 environment.
    """
    ips = []
    try:
        for if_name, addrs in psutil.net_if_addrs().items():
            if if_name == 'lo':
                continue
            for addr in addrs:
                if addr.family != socket.AF_INET:
                    continue
                try:
                    ip = ipaddress.IPv4Address(addr.address)
                except ValueError:
                    continue
                if ip.is_loopback or ip.is_link_local:
                    continue
                if ip not in ips:
                    ips.append(ip)
    except Exception:
        pass
    return ips

def _build_san_entries(host: str):
    san_dns = ["localhost"]
    san_ip  = [ipaddress.IPv4Address("127.0.0.1")]
    # Add hostname and hostname.local for mDNS access
    try:
        hostname = socket.gethostname().strip()
        for name in [f"{hostname}", f"{hostname.lower()}", f"{hostname}.local", f"{hostname.lower()}.local"]:
            if name and name not in san_dns:    san_dns.append(name)
    except Exception:
        pass
    # Add the configured mDNS hostname (Config.mdns_name) advertised by discovery_mdns.py
    try:
        from discovery_mdns import normalise_mdns_name
        mdns_name = normalise_mdns_name(getattr(Config, 'mdns_name', None))
        if mdns_name not in san_dns:
            san_dns.append(mdns_name)
    except Exception:
        pass
    # Add all current LAN IPs for direct IP access
    for lan_ip in _get_local_ips():
        if lan_ip not in san_ip:                san_ip.append(lan_ip)
    # Add configured host if specific
    if host and host.strip() and host not in ("0.0.0.0", "::"):
        try:
            ip = ipaddress.ip_address(host)
            if ip not in san_ip:                san_ip.append(ip)
        except ValueError:
            if host not in san_dns:             san_dns.append(host)    
    return san_dns, san_ip

# ── Certificate generation ─────────────────────────────────────────────────────────────

def _load_or_generate_ca_cert(logger):
    """
    Load the existing CA cert+key from disk, or generate a new one if missing
    or unreadable. The CA is long-lived (10 yrs) and must remain stable —
    users install it into their trust store once and it should never change.
    Returns (ca_cert, ca_key, ca_name).
    """
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    if CA_CERT_PATH.is_file() and CA_KEY_PATH.is_file():
        try:
            ca_cert = x509.load_pem_x509_certificate(CA_CERT_PATH.read_bytes(), default_backend())
            ca_key  = load_pem_private_key(CA_KEY_PATH.read_bytes(), password=None, backend=default_backend())
            remaining = ca_cert.not_valid_after_utc - datetime.datetime.now(datetime.timezone.utc)
            if remaining.days > 30:
                return ca_cert, ca_key, ca_cert.subject
        except Exception as exc:
            pass
    # Generate new CA
    ca_key  = _new_rsa_key()
    ca_name = _make_name("alpaca-pilot-ca")
    ca_cert = _build_cert(
        subject=ca_name, issuer=ca_name,
        public_key=ca_key.public_key(), signing_key=ca_key,
        days=3650,
        extensions=[
            (x509.BasicConstraints(ca=True, path_length=0), True),
            (x509.KeyUsage(
                digital_signature=False,  key_cert_sign=True,  crl_sign=True,
                content_commitment=False, key_encipherment=False,
                data_encipherment=False,  key_agreement=False,
                encipher_only=False,      decipher_only=False,
            ), True),
            (x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False),
        ],
    )
    CA_CERT_PATH.write_bytes(_pem_cert(ca_cert))
    CA_KEY_PATH.write_bytes(_pem_key(ca_key))
    _chmod(CA_CERT_PATH,0o644)
    _chmod(CA_KEY_PATH, 0o600)
    logger.info(f"==STARTUP== CA certificate generated {CA_CERT_PATH}")
    logger.info(f"==STARTUP== Install CA cert into browser/OS trust store: {CA_CERT_PATH}")
    return ca_cert, ca_key, ca_name 

def _load_or_generate_server_cert(host: str, ca_cert, ca_key, ca_name, logger) -> bool:
    """
    Load the existing server cert if still valid, or generate a new one signed
    by the given CA. Short-lived (397 days — Chrome's maximum).
    Returns True if a usable cert/key pair is available.
    """
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    if TLS_CERT_PATH.is_file() and TLS_KEY_PATH.is_file():
        try:
            pem = TLS_CERT_PATH.read_bytes()
            cert = x509.load_pem_x509_certificate(pem, default_backend())
            remaining = cert.not_valid_after_utc - datetime.datetime.now(datetime.timezone.utc)
            # Also check the mDNS name is present 
            from discovery_mdns import normalise_mdns_name
            wanted_mdns = normalise_mdns_name(getattr(Config, 'mdns_name', None))
            san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            existing_dns = set(san_ext.get_values_for_type(x509.DNSName))
            if remaining.days > 30 and wanted_mdns in existing_dns:
                return True
        except Exception:
            pass
    # Generate new Server Cert
    try:
        san_dns, san_ip = _build_san_entries(host)
        san_ext = x509.SubjectAlternativeName(
            [x509.DNSName(d) for d in san_dns] + [x509.IPAddress(ip) for ip in san_ip]
        )
        server_key  = _new_rsa_key()
        server_cert = _build_cert(
            subject=_make_name("alpaca-pilot"), issuer=ca_name,
            public_key=server_key.public_key(), signing_key=ca_key,
            days=397,
            extensions=[
                (san_ext,                                                                 False),
                (x509.BasicConstraints(ca=False, path_length=None),                       True),
                (x509.KeyUsage(
                    digital_signature=True,  key_encipherment=True,
                    content_commitment=False, data_encipherment=False,
                    key_agreement=False,     key_cert_sign=False,
                    crl_sign=False,          encipher_only=False, decipher_only=False,
                ), True),
                (x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH]),            False),
                (x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()),       False),
                (x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),  False),
            ],
        )
        TLS_CERT_PATH.write_bytes(_pem_cert(server_cert) + _pem_cert(ca_cert))
        TLS_KEY_PATH.write_bytes(_pem_key(server_key))
        _chmod(TLS_CERT_PATH, 0o644)
        _chmod(TLS_KEY_PATH,  0o600)
        logger.info(f"==STARTUP== Server cert generated {TLS_CERT_PATH} (397 days)")
        logger.info(f"==STARTUP== TLS SANs: {san_dns + [str(i) for i in san_ip]}")
        return True
    except Exception as exc:
        logger.exception(f"==TLS== Failed to generate server certificate: {exc}")
        return False

def ensure_tls_cert(host: str, logger) -> bool:
    """
    Ensure a valid CA + server certificate pair exists in DATA_DIR.
      CA cert     — loaded if present, generated once if not (stable for trust store)
      Server cert — loaded if valid, regenerated when missing or expiring within 30 days
    Returns True if a usable cert/key pair is available.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ca_cert, ca_key, ca_name = _load_or_generate_ca_cert(logger)
    success = _load_or_generate_server_cert(host, ca_cert, ca_key, ca_name, logger)
    return success

# ── Falcon resources ─────────────────────────────────────────────────────────────

class CACertDownloadResource:
    async def on_get(self, req, resp):
        if not CA_CERT_PATH.is_file():
            resp.status = '404 Not Found'
            return
        resp.content_type = 'application/x-x509-ca-cert'
        resp.set_header('Content-Disposition', 'attachment; filename="alpaca_pilot_ca.crt"')
        async with aiofiles.open(CA_CERT_PATH, 'rb') as f:
            resp.data = await f.read()

class QuasarStaticResource:
    async def on_get(self, req, resp, path=None):
        requested_path = path or 'index.html'
        file_path = QUASAR_DIST / requested_path
        if not os.path.isfile(file_path):
            file_path = QUASAR_DIST / 'index.html'  # fallback for SPA routing

        resp.content_type = mimetypes.guess_type(file_path)[0] or 'text/html'
        async with aiofiles.open(file_path, 'rb') as f:
            resp.data = await f.read()


class AsyncStaticResource:
    def __init__(self, base_path: Path):
        self.base_path = base_path

    async def on_get(self, req, resp, filename):
        file_path = self.base_path / filename
        if not file_path.is_file():
            resp.status = '404 Not Found'
            return
        resp.content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        async with aiofiles.open(file_path, 'rb') as f:
            resp.data = await f.read()


class HttpsRedirectResource:
    """
    Catches every HTTP request and issues a permanent redirect to the
    equivalent HTTPS URL on the configured HTTPS port.
    """
    def __init__(self, https_port: int):
        self.https_port = https_port

    async def on_get(self, req, resp, ws=None, **kwargs):
        if ws is not None:
            # WebSockets can't follow an HTTP redirect — refuse cleanly.
            await ws.close(code=1002)
            return
        host = req.host.split(':')[0]   # strip any existing port
        port_suffix = '' if self.https_port == 443 else f':{self.https_port}'
        resp.status  = HTTP_301
        resp.location = f'https://{host}{port_suffix}{req.path}'
        if req.query_string:
            resp.location += f'?{req.query_string}'

class HttpRedirectResource:
    """
    Redirects HTTPS requests to plain HTTP on the configured HTTP port.
    Used when enable_https=False so bookmarked https:// URLs still work.
    """
    def __init__(self, http_port: int):
        self.http_port = http_port

    async def on_get(self, req, resp, ws=None, **kwargs):
        if ws is not None:
            # WebSockets can't follow an HTTP redirect — refuse cleanly.
            await ws.close(code=1002)
            return
        host = req.host.split(':')[0]
        port_suffix = '' if self.http_port == 80 else f':{self.http_port}'
        resp.status = HTTP_301
        resp.location = f'http://{host}{port_suffix}{req.path}'
        if req.query_string:
            resp.location += f'?{req.query_string}'

class AlpacaProxyResource:
    def __init__(self, api_base: str):
        self.api_base = api_base
        self._session: aiohttp.ClientSession = None

    def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(base_url=self.api_base)
        return self._session

    async def on_get(self, req, resp, path=''):
        await self._proxy(req, resp, 'GET', path)

    async def on_put(self, req, resp, path=''):
        await self._proxy(req, resp, 'PUT', path)

    async def on_options(self, req, resp, path=''):
        resp.status = HTTP_200

    async def _proxy(self, req, resp, method, path):
        url = f'/{path}'
        if req.query_string:
            url += f'?{req.query_string}'
        body = await req.bounded_stream.read() if method == 'PUT' else None
        headers = {'Content-Type': req.content_type} if body else {}
        try:
            async with self._get_session().request(method, url, data=body, headers=headers) as r:
                resp.status = str(r.status)
                resp.content_type = r.headers.get('Content-Type', 'application/json')
                resp.data = await r.read()
        except aiohttp.ClientError as e:
            resp.status = '502 Bad Gateway'
            resp.media = {'error': str(e)}

class AlpacaSocketProxyResource:
    """
    Proxies a browser WebSocket (on the pilot's own origin) through to the
    internal Alpaca Pilot socket server (app_socket.py), mirroring how
    AlpacaProxyResource proxies REST calls. This means the frontend never
    needs to know the real device hostname/IP for the socket connection —
    same as REST.
    """
    def __init__(self, socket_base: str):
        self.socket_base = socket_base  # e.g. 'ws://localhost:5556' or 'wss://localhost:5556'

    async def on_websocket(self, req, ws):
        await ws.accept()
        connector = aiohttp.TCPConnector(ssl=False)  # internal hop, self-signed cert if wss
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.ws_connect(f'{self.socket_base}/ws') as upstream:
                    await self._relay(ws, upstream)
        except Exception:
            try:
                await ws.close(code=1011)
            except Exception:
                pass

    async def _relay(self, client_ws, upstream_ws):
        async def client_to_upstream():
            try:
                while True:
                    msg = await client_ws.receive_text()
                    await upstream_ws.send_str(msg)
            except (WebSocketDisconnected, ConnectionResetError):
                pass

        async def upstream_to_client():
            async for msg in upstream_ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        await client_ws.send_text(msg.data)
                    except WebSocketDisconnected:
                        break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.ERROR):
                    break

        tasks = [asyncio.create_task(client_to_upstream()), asyncio.create_task(upstream_to_client())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()

# ── Version Watchdog Falcon Resource ─────────────────────────────────────────────────────────────

class VersionResource:
    def __init__(self):
        # capture once at Driver start/Resource initialisation
        self._boot_token = hex(int(time.time()))[2:]    # changes every Driver restart
        self._https_active = Config.enable_https        # capture state when Driver starts and becomes active
        self._spa_hash_cached = None                    # changes every Alpaca Pilot SPA rebuild
        self._spa_hash_cached = self._get_spa_hash()    # cache in case index.html is temporarily deleted during a rebuild
        self._index_path = QUASAR_DIST / 'index.html'

    def _get_spa_hash(self) -> str:
        """Hash the main SPA index.html to detect new builds."""
        try:
            if self._index_path.is_file():
                self._spa_hash_cached = hashlib.md5(self._index_path.read_bytes()).hexdigest()[:8]
        except Exception:
            pass
        return self._spa_hash_cached or 'unknown'

    async def on_get(self, req, resp):
        resp.media = {
            'boot':  self._boot_token,
            'https': self._https_active,
            'spa':   self._get_spa_hash(),                   
            'driver': DeviceMetadata.Version
        }



# ── MAIN HTTP/HTTPS ENGINE (FALCON ASGI + UVICORN) ─────────────────────────────────────────────────────────────

async def alpaca_pilot_httpd(logger, lifecycle: LifecycleController):
    """
    Start the Alpaca Pilot web server.

    Behaviour:
      • If TLS cert generation succeeds → serves the Quasar SPA over HTTPS and
        runs a tiny HTTP server on Config.alpaca_pilot_http_port (default 80)
        that redirects all traffic to HTTPS.  Clipboard and Geolocation APIs
        will work because the browser sees a secure context.
      • If cert generation fails (e.g. 'cryptography' not installed) → falls
        back to plain HTTP on Config.alpaca_pilot_http_port so the app still loads,
        but clipboard/location features remain restricted.

    Config keys used:
      alpaca_restapi_ip_address   – bind address (e.g. "0.0.0.0")
      alpaca_pilot_https_port     – HTTPS port  (default 443)
      alpaca_pilot_http_port      – HTTP redirect port (default 80)
      enable_pilot                – bool gate
    """
    if not Config.enable_pilot:
        return

    bind_host   = Config.alpaca_restapi_ip_address
    https_port  = getattr(Config, 'alpaca_pilot_https_port', 443)
    http_port   = getattr(Config, 'alpaca_pilot_http_port', 80)

    # Both ports are used regardless of which branch (HTTPS+redirect or HTTP+redirect)
    # runs below, so check both up front and fail with one clear message.
    for port in (https_port, http_port):
        bind_err = check_port_bindable(bind_host, port)
        if bind_err is not None:
            logger.error("==STARTUP FAILED== " + describe_bind_error(bind_err, bind_host, port, "Alpaca Pilot Web"))
            await lifecycle.signal(LifecycleEvent.SHUTDOWN)
            return

    # --- TLS cert -----------------------------------------------------------
    tls_ok = Config.enable_https and ensure_tls_cert(bind_host, logger)
    version_resource = VersionResource()

    # --- Build the main (HTTPS or fallback HTTP) Falcon app -----------------
    main_app = asgi.App()
    main_app.add_route('/icons/{filename}',    AsyncStaticResource(QUASAR_DIST / 'icons'))
    main_app.add_route('/assets/{filename}',   AsyncStaticResource(QUASAR_DIST / 'assets'))
    main_app.add_route('/{path}',              QuasarStaticResource())
    main_app.add_route('/',                    QuasarStaticResource())
    main_app.add_route('/alpaca_pilot_ca.crt', CACertDownloadResource())
    main_app.add_route('/version',             version_resource)
    # --- Forward the HTTPS/HTTP webserver /proxy routes to the main REST-API Falcon app/port -----------------
    proto = 'HTTPS' if Config.enable_rest_https else 'HTTP'
    proxy = AlpacaProxyResource(f'{proto}://localhost:{Config.alpaca_restapi_port}')
    main_app.add_route('/proxy/{path:path}',   proxy)
    main_app.add_route('/proxy',               proxy)
    # --- Forward /proxy/ws to the internal socket server (app_socket.py) -------------------------------------
    socket_proto = 'wss' if Config.enable_https else 'ws'
    socket_proxy = AlpacaSocketProxyResource(f'{socket_proto}://localhost:{Config.alpaca_socket_port}')
    main_app.add_route('/proxy/ws', socket_proxy)
    
    servers_to_run = []

    if tls_ok:
        # HTTPS server for the Quasar SPA
        # timeout_graceful_shutdown bounds the connection-drain wait; default is None
        # (waits forever for open connections) -- a browser tab left open on the Pilot
        # SPA holds a keep-alive/WSS connection that would otherwise hang shutdown indefinitely.
        https_cfg = uvicorn.Config(main_app, host=bind_host, port=https_port, ssl_certfile=str(TLS_CERT_PATH), ssl_keyfile=str(TLS_KEY_PATH), log_level="error", log_config=None, timeout_graceful_shutdown=3)
        https_server = uvicorn.Server(https_cfg)
        servers_to_run.append(('HTTPS', https_server, https_port))

        # HTTP redirect server
        redirect_app = asgi.App()
        redirect_resource = HttpsRedirectResource(https_port)
        redirect_app.add_route('/version',             version_resource)
        redirect_app.add_sink(redirect_resource.on_get, prefix='/')
        http_redirect_cfg = uvicorn.Config(redirect_app, host=bind_host, port=http_port, log_level="error", log_config=None, timeout_graceful_shutdown=3)
        http_server = uvicorn.Server(http_redirect_cfg)
        servers_to_run.append(('HTTP-redirect', http_server, http_port))
        logger.info(f"==STARTUP== Serving Alpaca Pilot Web (HTTPS) on {bind_host}:{https_port} | (HTTP) redirect on {bind_host}:{http_port}")

    else:
        # HTTP server for the Quasar SPA
        http_cfg = uvicorn.Config(main_app, host=bind_host, port=http_port, log_level="error", log_config=None, timeout_graceful_shutdown=3)
        http_server = uvicorn.Server(http_cfg)
        servers_to_run.append(('HTTP', http_server, https_port))

        # HTTPS redirect server
        redirect_tls_ok = ensure_tls_cert(bind_host, logger)
        if redirect_tls_ok:
            redirect_app = asgi.App()
            redirect_app.add_route('/version',             version_resource)
            redirect_app.add_sink(HttpRedirectResource(http_port).on_get, prefix='/')
            https_redirect_cfg = uvicorn.Config(redirect_app, host=bind_host, port=https_port, ssl_certfile=str(TLS_CERT_PATH), ssl_keyfile=str(TLS_KEY_PATH), log_level="error", log_config=None, timeout_graceful_shutdown=3)
            https_redirect_server = uvicorn.Server(https_redirect_cfg)
            servers_to_run.append(('HTTPS-redirect', https_redirect_server, https_port))

        logger.info(f"==STARTUP== Serving Alpaca Pilot Web (HTTP) on {bind_host}:{http_port}")


    # --- Run all servers concurrently alongside lifecycle watcher -----------
    async def serve_all():
        await asyncio.gather(*[s.serve() for _, s, _ in servers_to_run])

    try:
        await asyncio.gather(
            lifecycle._wrap(serve_all()),
            lifecycle.wait_for_event(),
        )
    except asyncio.CancelledError:
        logger.info("==CANCELLED== Alpaca Web Server cancel received.")
    except Exception as e:
        logger.exception(f"==EXCEPTION== Alpaca Web Server unhandled exception: {e}")
    finally:
        logger.info("==SHUTDOWN== Alpaca Web Server shutting down.")
        for name, server, port in servers_to_run:
            if server and server.started:
                logger.info(f"==SHUTDOWN== Stopping {name} server on port {port}.")
                await server.shutdown()