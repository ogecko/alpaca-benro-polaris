# -*- coding: utf-8 -*-

import asyncio
import socket
import json
import os
from logging import Logger
from config import Config
from shr import LifecycleController, LifecycleEvent
import struct

async def socket_client(logger: Logger, lifecycle: LifecycleController):
    if not Config.enable_discovery:
        return

    # create the responder and run it until a lifecyle event
    responder = AlpacaDiscoveryResponder(logger)
    while not lifecycle.should_shutdown():
        try:
            await responder.start()
        finally:
            logger.info("==SHUTDOWN== Alpaca Discovery Service shutting down.")
            await responder.stop()


DISCOVERY_KEYWORD = "alpacadiscovery1"
IPV6_GROUP = "ff12::a1:9aca"

class AlpacaDiscoveryResponder:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.poll_interval = 0.1
        self.running = False
        self.response_to_send = json.dumps({"AlpacaPort": Config.alpaca_restapi_port}).encode()
        self.ipv4_rsock = None
        self.ipv6_rsock = None
        self.ipv4_tsock = None
        self.ipv6_tsock = None

    def _create_ipv4_transmit_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)
        return sock

    def _create_ipv6_transmit_socket(self):
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)
        return sock

    def _create_ipv4_receive_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", Config.alpaca_discovery_port))
        sock.setblocking(False)
        return sock

    def _create_ipv6_receive_socket(self):
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("::", Config.alpaca_discovery_port))
        group_bin = socket.inet_pton(socket.AF_INET6, IPV6_GROUP)
        mreq = group_bin + struct.pack("@I", 0)  # interface index 0 = all
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
        sock.setblocking(False)
        return sock

    def _create_transmit_socket(self):
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)
        return sock

    async def _poll_socket(self, sock, label):
        loop = asyncio.get_running_loop()
        while self.running:
            try:
                data, addr = await asyncio.to_thread(sock.recvfrom, 1024)
                message = data.decode("ascii", errors="ignore")
                if DISCOVERY_KEYWORD in message:
                    self.logger.info(f"{label} Discovery request from {addr}: {message}")
                    if isinstance(addr, tuple) and len(addr) == 2:
                        await asyncio.to_thread(self.ipv4_tsock.sendto, self.response_to_send, addr)                         
                    elif isinstance(addr, tuple) and len(addr) == 4:
                        await asyncio.to_thread(self.ipv6_tsock.sendto, self.response_to_send, addr) 
                    else:
                        self.logger.warning(f"Unknown address format: {addr}")
                    self.logger.info(f"{label} Sent response to {addr}")
            except BlockingIOError:
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                self.logger.warning(f"{label} Discovery error: {e}")
                await asyncio.sleep(self.poll_interval)

    async def start(self):
        self.ipv4_rsock = self._create_ipv4_receive_socket()
        self.ipv6_rsock = self._create_ipv6_receive_socket()
        self.ipv4_tsock = self._create_ipv4_transmit_socket()
        self.ipv6_tsock = self._create_ipv6_transmit_socket()
        self.tsock = self._create_transmit_socket()
        self.running = True
        self.logger.info(f"==STARTUP== Serving Alpaca Discovery on :{Config.alpaca_discovery_port}")
        await asyncio.gather(
            self._poll_socket(self.ipv4_rsock, "IPv4"),
            self._poll_socket(self.ipv6_rsock, "IPv6")
        )

    async def stop(self):
        self.running = False
        for sock in [self.ipv4_rsock, self.ipv6_rsock, self.ipv4_tsock, self.ipv6_tsock]:
            if sock:
                sock.close()
