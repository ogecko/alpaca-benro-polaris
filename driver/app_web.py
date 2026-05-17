# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# app_web.py - Alpaca Pilot Web Application module
# -----------------------------------------------------------------------------
# MIT License
#
# Copyright (c) 2025 David Morrison
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# -----------------------------------------------------------------------------
import os
import mimetypes
import aiofiles
import asyncio
import uvicorn
from falcon import asgi, HTTP_200, HTTP_301
from config import Config
from pathlib import Path
from shr import LifecycleController
import datetime
import ipaddress
import logging

SCRIPT_DIR = Path(__file__).resolve().parent            # Get the path to the current script
QUASAR_DIST = SCRIPT_DIR.parent / 'pilot' / 'dist' / 'spa'
DATA_DIR    = SCRIPT_DIR.parent / 'data'                # ../data relative to main.py location

# TLS certificate/key paths (generated once, reused across runs)
TLS_CERT_PATH = DATA_DIR / 'alpaca_pilot.crt'
TLS_KEY_PATH  = DATA_DIR / 'alpaca_pilot.key'

# How long the self-signed cert is valid for (10 years — nobody wants to redo this)
CERT_VALIDITY_DAYS = 3650


# ---------------------------------------------------------------------------
# Certificate helpers
# ---------------------------------------------------------------------------

def _cert_needs_regeneration(cert_path: Path, key_path: Path) -> bool:
    """Return True if cert/key are missing OR the cert expires within 30 days."""
    if not cert_path.is_file() or not key_path.is_file():
        return True
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        pem = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(pem, default_backend())
        # naive datetime comparison — both are UTC
        remaining = cert.not_valid_after_utc - datetime.datetime.now(datetime.timezone.utc)
        return remaining.days < 30
    except Exception:
        return True  # if we can't read it, regenerate


def _generate_self_signed_cert(host: str, cert_path: Path, key_path: Path, logger) -> bool:
    """
    Generate a self-signed TLS certificate and private key, saving them to
    cert_path / key_path.  Works on Windows, macOS, and Linux with Python 3.9+
    as long as the 'cryptography' package is installed (pip install cryptography).

    Subject Alternative Names include:
      - The configured host/IP so the cert matches the server address.
      - localhost / 127.0.0.1 so local loopback always works too.

    Returns True on success, False on any error.
    """
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend

        # --- private key ---
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

        # --- subject / issuer ---
        # COMMON_NAME must be 1-64 chars; browsers ignore it in favour of SANs
        # anyway, so we use a fixed safe string rather than the bind address
        # (which may be "0.0.0.0" or empty).
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "alpaca-pilot"),
        ])

        # --- build SAN list ------------------------------------------------
        # Include whatever address the driver is bound to plus sensible defaults
        san_dns  = ["localhost"]
        san_ip   = [ipaddress.IPv4Address("127.0.0.1")]

        # Add the configured host if it looks like an IP, otherwise as a DNS name
        if host not in ("0.0.0.0", "::"):
            try:
                san_ip.append(ipaddress.ip_address(host))
            except ValueError:
                san_dns.append(host)   # it's a hostname, not an IP

        # If bound to 0.0.0.0 we can't know the LAN IP at cert-generation time,
        # so we add the wildcard DNS fallback and a note in the log.
        san_entries = (
            [x509.DNSName(d) for d in san_dns]
            + [x509.IPAddress(ip) for ip in san_ip]
        )
        # --- certificate ---
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=CERT_VALIDITY_DAYS))
            .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256(), default_backend())
        )

        # --- persist to disk ---
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

        logger.info(
            f"==STARTUP== TLS cert generated → {cert_path}  "
            f"(valid {CERT_VALIDITY_DAYS // 365} yrs, SANs: {san_dns + [str(i) for i in san_ip]})"
        )
        return True

    except ImportError:
        logger.error(
            "==TLS== 'cryptography' package not found. "
            "Install it with:  pip install cryptography\n"
            "HTTPS will not be available; falling back to HTTP."
        )
        return False
    except Exception as exc:
        logger.exception(f"==TLS== Failed to generate self-signed certificate: {exc}")
        return False


def ensure_tls_cert(host: str, logger) -> bool:
    """
    Ensure a valid TLS certificate exists in DATA_DIR.
    Creates the data directory if needed, regenerates the cert if missing or
    expiring soon.  Returns True if a usable cert/key pair is available.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if _cert_needs_regeneration(TLS_CERT_PATH, TLS_KEY_PATH):
        logger.info("==STARTUP== Generating self-signed TLS certificate for HTTPS…")
        return _generate_self_signed_cert(host, TLS_CERT_PATH, TLS_KEY_PATH, logger)

    return True


# ---------------------------------------------------------------------------
# Falcon resources
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# MAIN HTTP/HTTPS ENGINE (FALCON ASGI + UVICORN)
# ---------------------------------------------------------------------------

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
    main_app.add_route('/icons/{filename}',  AsyncStaticResource(QUASAR_DIST / 'icons'))
    main_app.add_route('/assets/{filename}', AsyncStaticResource(QUASAR_DIST / 'assets'))
    main_app.add_route('/{path}',            QuasarStaticResource())
    main_app.add_route('/',                  QuasarStaticResource())

    servers_to_run = []

    if tls_ok:
        # HTTPS server for the Quasar SPA
        https_cfg = uvicorn.Config(
            main_app,
            host=bind_host,
            port=https_port,
            ssl_certfile=str(TLS_CERT_PATH),
            ssl_keyfile=str(TLS_KEY_PATH),
            log_level="error",
        )
        https_server = uvicorn.Server(https_cfg)
        servers_to_run.append(('HTTPS', https_server, https_port))

        # HTTP redirect server
        redirect_app = asgi.App()
        redirect_resource = HttpsRedirectResource(https_port)
        # Register a sink so *every* path is caught (Falcon sink = catch-all)
        redirect_app.add_sink(redirect_resource.on_get, prefix='/')

        http_cfg = uvicorn.Config(
            redirect_app,
            host=bind_host,
            port=http_port,
            log_level="error",
        )
        http_server = uvicorn.Server(http_cfg)
        servers_to_run.append(('HTTP-redirect', http_server, http_port))

        logger.info(f"==STARTUP== Serving Alpaca Pilot Web (HTTPS) on {bind_host}:{https_port} | (HTTP) redirect on {bind_host}:{http_port}")
        logger.warning("==STARTUP== Accept self-signed certificate warning on first visit — click 'Advanced > Proceed'")
    else:
        http_cfg = uvicorn.Config(
            main_app,
            host=bind_host,
            port=http_port,   # keep same port expectation
            log_level="error",
        )
        http_server = uvicorn.Server(http_cfg)
        servers_to_run.append(('HTTP', http_server, https_port))

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