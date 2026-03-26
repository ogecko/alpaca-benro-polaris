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
        self.response_to_send = json.dumps({"AlpacaPort": Config.alpaca_restapi_port}).encode()
        self.ipv4_rsock = None
        self.ipv6_rsock = None
        self.ipv4_tsock = None
        self.ipv6_tsock = None

    # ------------------------------------------------------------------
    # Socket constructors
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
        sock.setblocking(False)
        return sock

    def _create_ipv4_transmit_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)
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

        sock.setblocking(False)
        return sock

    def _create_ipv6_transmit_socket(self):
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Allow sending to link-local and site-local scopes.
        try:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        except OSError:
            pass
        sock.setblocking(False)
        return sock

    # ------------------------------------------------------------------
    # Polling loop — one per receive socket
    # ------------------------------------------------------------------

    async def _poll_socket(self, rsock, tsock, label: str):
        """
        Wait for discovery broadcasts/multicasts and reply on the matching
        transmit socket.  Uses loop.sock_recvfrom so the event loop drives
        readiness; avoids spinning on BlockingIOError.
        """
        if rsock is None:
            return

        loop = asyncio.get_running_loop()

        while self.running:
            try:
                data, addr = await loop.sock_recvfrom(rsock, 1024)
            except OSError as e:
                # Socket was closed during shutdown — exit cleanly.
                if not self.running:
                    return
                self.logger.warning(f"{label} recv error: {e}")
                await asyncio.sleep(0.1)
                continue

            try:
                message = data.decode("ascii", errors="ignore")
            except Exception:
                continue

            if DISCOVERY_KEYWORD not in message:
                continue

            if Config.log_alpaca_discovery:
                self.logger.info(f"{label} Discovery request from {addr}: {message!r}")

            try:
                await loop.sock_sendto(tsock, self.response_to_send, addr)
                if Config.log_alpaca_discovery:
                    self.logger.info(f"{label} Sent response to {addr}")
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