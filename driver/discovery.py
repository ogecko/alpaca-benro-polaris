# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# discovery.py - Discovery Responder for Alpaca Device
#
# Part of the AlpycaDevice Alpaca skeleton/template device driver
#
# Author:   Robert B. Denny <rdenny@dc3.com> (rbd)
#
# Python Compatibility: Requires Python 3.7 or later
# GitHub: https://github.com/ASCOMInitiative/AlpycaDevice
#
# -----------------------------------------------------------------------------
# MIT License
#
# Copyright (c) 2022 Bob Denny
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
# Edit History:
#
# 17-Dec-2022   rbd 0.1 Initial edit for Alpaca sample/template
# 19-Dec-2022   rbd 0.1 Validated with ConformU discovery diagnostics
#               Add thread name 'Discovery'
# 24-Dec-2022   rbd 0.1 Logging
# 25-Dec-2022   rbd 0.1 Logging typing for intellisense
# 27-Dec-2022   rbd 0.1 MIT license and module header. No mcast on device, duh!
#

import asyncio
import socket
import json
import os
from logging import Logger
from config import Config
from shr import LifecycleController, LifecycleEvent

async def socket_client(logger: Logger, lifecycle: LifecycleController):
    if Config.enable_discovery:
        responder = AsyncDiscoveryResponder(logger)
        task = asyncio.create_task(responder.run())

        while True:
            event = await lifecycle.wait_for_event()
            if event in (LifecycleEvent.SHUTDOWN, LifecycleEvent.RESTART, LifecycleEvent.INTERRUPT):
                responder.stop()
                await task
                break


class AsyncDiscoveryResponder:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.running = True
        self.ADDR = Config.alpaca_restapi_ip_address
        self.PORT = Config.alpaca_restapi_port
        self.device_address = (self.ADDR, Config.alpaca_discovery_port)
        self.alpaca_response = json.dumps({"AlpacaPort": self.PORT})

    async def run(self):
        loop = asyncio.get_running_loop()

        # Receive socket
        self.rsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if os.name != 'nt':
            self.rsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.rsock.bind(self.device_address)
        self.rsock.setblocking(False)

        # Transmit socket
        self.tsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tsock.bind((self.ADDR, 0))
        self.tsock.setblocking(False)

        self.logger.info(f'==STARTUP== Serving Alpaca Discovery Socket on {self.device_address[0]}:{self.device_address[1]}')

        try:
            while self.running:
                try:
                    data, addr = await asyncio.wait_for(loop.sock_recvfrom(self.rsock, 1024), timeout=2.0)
                except asyncio.TimeoutError:
                    continue  # check self.running again
                datascii = data.decode('ascii', errors='ignore')
                self.logger.info(f'Disc rcv {datascii} from {addr}')
                if 'alpacadiscovery1' in datascii:
                    await loop.sock_sendto(self.tsock, self.alpaca_response.encode(), addr)
        except asyncio.CancelledError:
            self.logger.info("[Discovery] CancelledError received.")
        finally:
            self.logger.info("==CANCELLED== Alpaca Discovery Server cancelled.")
            self.rsock.close()
            self.tsock.close()

    def stop(self):
        self.running = False
