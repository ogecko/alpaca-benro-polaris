# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# discovery_mdns.py - mDNS (Bonjour/Zeroconf) hostname advertisement module
#
# Publishes Config.mdns_name (e.g. "alpacapilot.local") on this host's LAN-facing
# IPv4 address, so an iPad/browser typing http://alpacapilot.local resolves
# straight to the Alpaca Pilot web server rather than to a stray IPv6 record,
# or to the Benro Polaris's own Wifi adapter (the driver host has two adapters).
#
# We run our own responder (via the `zeroconf` package) instead of relying on
# the OS's mDNS responder (Bonjour on macOS, avahi-daemon on Linux, nothing at
# all on Windows unless Bonjour/iTunes/a printer driver installed it). This
# keeps behaviour identical and controllable on every supported platform:
# Windows, Linux, macOS, and Raspberry Pi.
#
# We only ever publish an A (IPv4) record for the advertised name — never
# AAAA — which is what avoids the iOS/Safari "prefers IPv6, picks the wrong
# adapter" problem this module was written to fix.
# -----------------------------------------------------------------------------
import asyncio
import socket
import ipaddress
from logging import Logger

import psutil
from zeroconf import IPVersion, NonUniqueNameException, ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

from config import Config
from shr import LifecycleController

logger: Logger = None   # patched in by main.py, matching the rest of the app


def normalise_mdns_name(name: str) -> str:
    """
    Ensure the configured name always ends in the reserved '.local' mDNS
    domain (RFC 6762 S3) — browsers and OS resolvers only attempt mDNS
    resolution for that TLD, so a bare "alpacapilot" would silently fail.
    """
    name = (name or '').strip().rstrip('.')
    if not name:
        name = 'alpacapilot'
    if not name.lower().endswith('.local'):
        name += '.local'
    return name


def get_polaris_network() -> ipaddress.IPv4Network:
    """
    Network owned by the Benro Polaris's own Wifi adapter, derived from
    Config.polaris_ip_address. The Polaris always presents as a /24
    (e.g. 192.168.0.1, driver host gets 192.168.0.x) so a /24 is assumed.
    """
    polaris_ip = getattr(Config, 'polaris_ip_address', '192.168.0.1')
    return ipaddress.ip_network(f'{polaris_ip}/24', strict=False)


def pick_lan_ipv4(log: Logger) -> str:
    """
    Pick this host's IPv4 address on the LAN-facing adapter (the one the
    iPad/browser is actually on) — never the Benro Polaris adapter's subnet,
    never loopback/link-local, and never IPv6. The box may have two Wifi adapters
    so "the" local IP is ambiguous; we resolve the ambiguity explicitly by
    excluding the Polaris subnet rather than guessing.
    """
    polaris_net = get_polaris_network()
    candidates = []
    try:
        for if_name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family != socket.AF_INET:
                    continue
                try:
                    ip = ipaddress.IPv4Address(addr.address)
                except ValueError:
                    continue
                if ip.is_loopback or ip.is_link_local:
                    continue
                if ip in polaris_net:
                    continue
                candidates.append((if_name, ip))
    except Exception as e:
        log.warning(f"==MDNS== Failed enumerating network interfaces: {e}")
        return None

    if not candidates:
        return None

    # Prefer a private LAN address if more than one candidate remains (rare -
    # would mean a third adapter, e.g. a USB/Ethernet dongle, is present).
    for if_name, ip in candidates:
        if ip.is_private:
            return str(ip)
    return str(candidates[0][1])


class MdnsResponder:
    """
    Thin wrapper around zeroconf's AsyncZeroconf, mirroring the
    start()/stop() lifecycle shape of discovery_alpaca.AlpacaDiscoveryResponder.
    """
    def __init__(self, log: Logger):
        self.logger = log
        self.aiozc: AsyncZeroconf = None
        self.service_info: ServiceInfo = None
        self.advertised_ip: str = None

    async def start(self, ipv4: str):
        mdns_name = normalise_mdns_name(getattr(Config, 'mdns_name', None))
        port = Config.alpaca_pilot_http_port
        short_name = mdns_name[:-len('.local')]  # strip suffix for the service instance name

        # Registering a ServiceInfo with `server=` also answers plain A-record
        # queries for that hostname directly (not just _http._tcp discovery),
        # which is what lets a browser resolve "http://alpacapilot.local".
        self.service_info = ServiceInfo(
            type_="_http._tcp.local.",
            name=f"{short_name}._http._tcp.local.",
            addresses=[socket.inet_aton(ipv4)],   # IPv4 ONLY - never advertise an IPv6 addr
            port=port,
            server=f"{mdns_name}.",               # trailing dot = FQDN, required by zeroconf
            properties={"path": "/"},
        )

        self.aiozc = AsyncZeroconf(ip_version=IPVersion.V4Only)
        try:
            await self.aiozc.async_register_service(self.service_info)
        except Exception:
            # Registration failed (e.g. a name conflict on the LAN) - don't
            # leak the multicast socket, and leave the responder in a clean
            # "not registered" state so the caller can safely retry later.
            await self.aiozc.async_close()
            self.aiozc = None
            self.service_info = None
            raise
        self.advertised_ip = ipv4
        self.logger.info(f"==STARTUP== Serving mDNS hostname http://{mdns_name} -> {ipv4}:{port}")

    async def stop(self):
        if self.aiozc:
            try:
                if self.service_info:
                    await self.aiozc.async_unregister_service(self.service_info)
                await self.aiozc.async_close()
            except Exception as e:
                self.logger.debug(f"==MDNS== Error during shutdown: {e}")
        self.aiozc = None
        self.service_info = None
        self.advertised_ip = None


# How often to check for a LAN IPv4 before the mDNS name is first advertised
# (driver may boot before the venue Wifi adapter has an address yet), and
# afterwards, how often to confirm the advertised IP is still current (DHCP
# renewal / adapter change). One cheap local interface-enumeration check per
# tick — re-registration with zeroconf only happens if something changed.
MDNS_POLL_INTERVAL_SEC = 60


# Main entry point - matches discovery_alpaca.socket_client's role: one task
# in main.py's tasks list, polling on the shared lifecycle controller in the
# same should_shutdown() style as the rest of the app.
async def mdns_client(log: Logger, lifecycle: LifecycleController):
    if not Config.enable_mdns:
        return

    responder = MdnsResponder(log)
    registered = False
    try:
        while not lifecycle.should_shutdown():
            current_ip = pick_lan_ipv4(log)

            if current_ip is None:
                if registered:
                    log.warning("==MDNS== LAN IPv4 no longer available — withdrawing mDNS advertisement.")
                    await responder.stop()
                    registered = False
                else:
                    log.info(f"==MDNS== No LAN IPv4 yet (excluding Polaris subnet) — retrying in {MDNS_POLL_INTERVAL_SEC}s.")

            elif not registered or current_ip != responder.advertised_ip:
                if registered:
                    log.info(f"==MDNS== LAN IPv4 changed ({responder.advertised_ip} -> {current_ip}) — re-registering.")
                    await responder.stop()
                try:
                    await responder.start(current_ip)
                    registered = True
                except NonUniqueNameException:
                    claimed_name = normalise_mdns_name(getattr(Config, 'mdns_name', None))
                    log.warning(
                        f"==MDNS== '{claimed_name}' is already claimed by another device on this "
                        f"network (e.g. a second driver instance, or the OS's own mDNS responder) "
                        f"— will retry in {MDNS_POLL_INTERVAL_SEC}s. Set a unique Config.mdns_name "
                        f"if this persists."
                    )
                    registered = False

            await asyncio.sleep(MDNS_POLL_INTERVAL_SEC)
    except asyncio.CancelledError:
        log.info("==CANCELLED== mDNS responder cancel received.")
    except Exception as e:
        log.exception(f"==EXCEPTION== mDNS responder unhandled exception: {e}")
    finally:
        log.info("==SHUTDOWN== mDNS responder shutting down.")
        await responder.stop()