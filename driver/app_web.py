# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# app_web.py - Alpaca Pilot Web Application module
# -----------------------------------------------------------------------------
import os
import mimetypes
import aiofiles
import asyncio
import uvicorn
import socket
from falcon import asgi, HTTP_200, HTTP_301
from config import Config
from pathlib import Path
from shr import LifecycleController
import datetime
import ipaddress


SCRIPT_DIR = Path(__file__).resolve().parent            # Get the path to the current script
QUASAR_DIST = SCRIPT_DIR.parent / 'pilot' / 'dist' / 'spa'
DATA_DIR    = SCRIPT_DIR.parent / 'data'                # ../data relative to main.py location

TLS_CERT_PATH = DATA_DIR / 'alpaca_pilot.crt'      # server cert + CA chain (for uvicorn)
TLS_KEY_PATH  = DATA_DIR / 'alpaca_pilot.key'      # server private key
CA_CERT_PATH  = DATA_DIR / 'alpaca_pilot_ca.crt'   # CA cert only (for trust store install)
CA_KEY_PATH   = DATA_DIR / 'alpaca_pilot_ca.key'   # CA private key

# For Nina to use Alpaca RestAPI over HTTPS, set Nina>Options>Equipment>Alpaca Discover - Enable HTTPS
# Also need to install Alpaca Pilot certificate on machine Nina is running on, using Admin Powershell eg.
# Import-Certificate -FilePath .\alpaca_pilot.crt -CertStoreLocation Cert:\LocalMachine\Root

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
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            addr = info[4][0]
            if not addr or not addr.strip():   
                continue
            try:
                ip = ipaddress.IPv4Address(addr)
                if not ip.is_loopback:
                    ips.append(ip)
            except ValueError:
                pass
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
            if remaining.days > 30:
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

    async def on_get(self, req, resp, **kwargs):
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

    async def on_get(self, req, resp, **kwargs):
        host = req.host.split(':')[0]
        port_suffix = '' if self.http_port == 80 else f':{self.http_port}'
        resp.status = HTTP_301
        resp.location = f'http://{host}{port_suffix}{req.path}'
        if req.query_string:
            resp.location += f'?{req.query_string}'



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

    # --- TLS cert -----------------------------------------------------------
    tls_ok = Config.enable_https and ensure_tls_cert(bind_host, logger)

    # --- Build the main (HTTPS or fallback HTTP) Falcon app -----------------
    main_app = asgi.App()
    main_app.add_route('/icons/{filename}',    AsyncStaticResource(QUASAR_DIST / 'icons'))
    main_app.add_route('/assets/{filename}',   AsyncStaticResource(QUASAR_DIST / 'assets'))
    main_app.add_route('/{path}',              QuasarStaticResource())
    main_app.add_route('/',                    QuasarStaticResource())
    main_app.add_route('/alpaca_pilot_ca.crt', CACertDownloadResource())

    servers_to_run = []

    if tls_ok:
        # HTTPS server for the Quasar SPA
        https_cfg = uvicorn.Config(main_app, host=bind_host, port=https_port, ssl_certfile=str(TLS_CERT_PATH), ssl_keyfile=str(TLS_KEY_PATH), log_level="error")
        https_server = uvicorn.Server(https_cfg)
        servers_to_run.append(('HTTPS', https_server, https_port))

        # HTTP redirect server
        redirect_app = asgi.App()
        redirect_resource = HttpsRedirectResource(https_port)
        redirect_app.add_sink(redirect_resource.on_get, prefix='/')
        http_redirect_cfg = uvicorn.Config(redirect_app, host=bind_host, port=http_port, log_level="error" )
        http_server = uvicorn.Server(http_redirect_cfg)
        servers_to_run.append(('HTTP-redirect', http_server, http_port))
        logger.info(f"==STARTUP== Serving Alpaca Pilot Web (HTTPS) on {bind_host}:{https_port} | (HTTP) redirect on {bind_host}:{http_port}")
        logger.warning("==STARTUP== Accept self-signed certificate warning on first visit — click 'Advanced > Proceed'")

    else:
        # HTTP server for the Quasar SPA
        http_cfg = uvicorn.Config(main_app, host=bind_host, port=http_port, log_level="error" )
        http_server = uvicorn.Server(http_cfg)
        servers_to_run.append(('HTTP', http_server, https_port))

        # HTTPS redirect server
        redirect_tls_ok = ensure_tls_cert(bind_host, logger)
        if redirect_tls_ok:
            redirect_app = asgi.App()
            redirect_app.add_sink(HttpRedirectResource(http_port).on_get, prefix='/')
            https_redirect_cfg = uvicorn.Config(redirect_app, host=bind_host, port=https_port, ssl_certfile=str(TLS_CERT_PATH), ssl_keyfile=str(TLS_KEY_PATH), log_level="error")
            https_redirect_server = uvicorn.Server(https_redirect_cfg)
            servers_to_run.append(('HTTPS-redirect', https_redirect_server, https_port))

        logger.info(f"==STARTUP== Serving Alpaca Pilot Web (HTTP) on {bind_host}:{https_port}")


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