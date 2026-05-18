# -*- coding: utf-8 -*-

import asyncio
import socket
import json
import struct
from logging import Logger
from config import Config
from shr import LifecycleController, LifecycleEvent

# Main entry point - create the discovery responder and run it until a lifecyle event
async def socket_client(logger: Logger, lifecycle: LifecycleController):
    if not Config.enable_discovery:
        return

    responder = AlpacaDiscoveryResponder(logger)
    while not lifecycle.should_shutdown():
        try:
            await responder.start()
        finally:
            logger.info("==SHUTDOWN== Alpaca Discovery Service shutting down.")
            await responder.stop()


# ASCOM Alpaca spec mandates this exact site-local multicast group.
IPV6_GROUP = "ff12::a1:9aca"
DISCOVERY_KEYWORD = "alpacadiscovery1"


class AlpacaDiscoveryResponder:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.running = False
        self.ipv4_rsock = None
        self.ipv6_rsock = None
        self.ipv4_tsock = None
        self.ipv6_tsock = None

    @property
    def _response(self):
        return json.dumps({
            "AlpacaPort": Config.alpaca_restapi_port,
            "Https": Config.enable_https,
        }).encode()

    # ------------------------------------------------------------------
    # Socket constructors
    # All sockets are left in blocking mode — recvfrom is called inside
    # asyncio.to_thread with a timeout, so blocking is correct here.
    # ------------------------------------------------------------------

    def _create_ipv4_receive_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # SO_REUSEPORT lets multiple processes share the port on Linux/macOS.
        # Not available on Windows; ignore if missing.
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", Config.alpaca_discovery_port))
        return sock

    def _create_ipv4_transmit_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock

    def _create_ipv6_receive_socket(self):
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass

        # Force IPv6-only so it does not fight the IPv4 socket on the same port.
        # This is the default on Windows but must be set explicitly on Linux/macOS.
        try:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        except OSError:
            pass

        # Bind to all IPv6 interfaces on the discovery port.
        sock.bind(("::", Config.alpaca_discovery_port, 0, 0))

        # Join the ASCOM multicast group on every available interface.
        group_bin = socket.inet_pton(socket.AF_INET6, IPV6_GROUP)
        joined = False
        for if_index, if_name in socket.if_nameindex():
            try:
                mreq = group_bin + struct.pack("@I", if_index)
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
                if Config.log_alpaca_discovery:
                    self.logger.info(f"Joined IPv6 multicast group {IPV6_GROUP} on {if_name}")
                joined = True
            except OSError as e:
                self.logger.debug(f"Skipping {if_name} for IPv6 multicast: {e}")

        if not joined:
            self.logger.warning("No IPv6 multicast interfaces available")

        return sock

    def _create_ipv6_transmit_socket(self):
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Allow sending to link-local and site-local scopes.
        try:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        except OSError:
            pass
        return sock

    # ------------------------------------------------------------------
    # Polling loop — one per receive socket
    # ------------------------------------------------------------------

    def _blocking_recvfrom(self, rsock):
        """
        Blocking recv with a 1 s timeout, safe to run inside asyncio.to_thread.
        Returns (data, addr) on success, or (None, None) on timeout.

        The 1 s timeout means the event loop checks self.running at least
        once per second, giving clean and prompt shutdown on all platforms.
        """
        rsock.settimeout(1.0)
        try:
            return rsock.recvfrom(1024)
        except socket.timeout:
            return None, None


    async def _poll_socket(self, rsock, tsock, label: str):
        """
        Wait for discovery broadcasts/multicasts and reply on the matching
        transmit socket.

        Uses asyncio.to_thread with a blocking socket + 1 s timeout so it
        never spins and yields back to the event loop each iteration.
        Compatible with Python 3.9+ on Windows, Linux, and macOS:
          - avoids loop.sock_recvfrom  (requires Python 3.11)
          - avoids loop.add_reader     (NotImplementedError on Windows ProactorEventLoop)
        """
        if rsock is None:
            return

        loop = asyncio.get_running_loop()
        
        def blocking_loop():
            while self.running:
                data, addr = self._blocking_recvfrom(rsock)
                if data is None:
                    continue
                # Schedule the response back on the event loop
                loop.call_soon_threadsafe(self._handle_discovery, data, addr, tsock, label)

        await asyncio.to_thread(blocking_loop)

    def _handle_discovery(self, data, addr, tsock, label):
        try:
            message = data.decode("ascii", errors="ignore")
        except Exception:
            return
        if DISCOVERY_KEYWORD not in message:
            return
        try:
            tsock.sendto(self._response, addr)
            if Config.log_alpaca_discovery:
                self.logger.info(f"{label} Discovery response sent to {addr}: {self._response!r}")
        except OSError as e:
            self.logger.warning(f"{label} Failed to send response to {addr}: {e}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        # IPv6 — attempt first; non-fatal if the OS has no IPv6 stack.
        try:
            self.ipv6_rsock = self._create_ipv6_receive_socket()
            self.ipv6_tsock = self._create_ipv6_transmit_socket()
        except Exception as e:
            self.logger.warning(f"IPv6 discovery disabled: {e}")
            self.ipv6_rsock = None
            self.ipv6_tsock = None

        # IPv4 — attempt second; also non-fatal.
        try:
            self.ipv4_rsock = self._create_ipv4_receive_socket()
            self.ipv4_tsock = self._create_ipv4_transmit_socket()
        except Exception as e:
            self.logger.warning(f"IPv4 discovery disabled: {e}")
            self.ipv4_rsock = None
            self.ipv4_tsock = None

        if self.ipv4_rsock is None and self.ipv6_rsock is None:
            self.logger.error("No discovery sockets available — discovery disabled")
            return

        self.running = True
        self.logger.info(f"==STARTUP== Serving Alpaca Discovery on :{Config.alpaca_discovery_port}")

        await asyncio.gather(
            self._poll_socket(self.ipv4_rsock, self.ipv4_tsock, "IPv4"),
            self._poll_socket(self.ipv6_rsock, self.ipv6_tsock, "IPv6"),
        )

    async def stop(self):
        self.running = False
        for sock in [self.ipv4_rsock, self.ipv6_rsock, self.ipv4_tsock, self.ipv6_tsock]:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
        self.ipv4_rsock = self.ipv6_rsock = None
        self.ipv4_tsock = self.ipv6_tsock = None