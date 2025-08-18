# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# management.py - Management API for  ALpaca device
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
# 17-Dec-2022   rbd 0.1 Initial edit for Alpaca sample/template
# 19-Dec-2022   rbd 0.1 Constants in shr.py
# 22-Dec-2022   rbd 0.1 Device metadata, Configuration
# 25-Dec-2022   rbd 0.1 Logging typing for intellisense
# 27-Dec-2022   rbd 0.1 Minimize imports. MIT license and module header.
#               Enhanced logging.
# 23-May-2023   rbd 0.2 Refactoring for  multiple ASCOM device type support
#               GitHub issue #1
#
from falcon import Request, Response
from shr import PropertyResponse, DeviceMetadata
from config import Config
from logging import Logger
# For each *type* of device served
from telescope import TelescopeMetadata
from rotator import RotatorMetadata

logger: Logger = None
#logger = None                   # Safe on Python 3.7 but no intellisense in VSCode etc.

def set_management_logger(lgr):
    global logger
    logger = lgr

# -----------
# APIVersions
# -----------
class apiversions:
    async def on_get(self, req: Request, resp: Response):
        apis = [ 1 ]                            # TODO MAKE CONFIG OR GLOBAL
        resp.text = await PropertyResponse(apis, req)

# -------------------------
# Alpaca Server Description
# -------------------------
class description:
    async def on_get(self, req: Request, resp: Response):
        desc = {
            'ServerName'   : DeviceMetadata.Description,
            'Manufacturer' : DeviceMetadata.Manufacturer,
            'Version'      : DeviceMetadata.Version,
            'Location'     : Config.location
            }
        resp.text = await PropertyResponse(desc, req)

# -----------------
# ConfiguredDevices
# -----------------
class configureddevices():
    async def on_get(self, req: Request, resp: Response):
        confarray = [    # ADD ONE FOR EACH DEVICE TYPE AND INSTANCE SERVED
            {
            'DeviceName'    : TelescopeMetadata.Name,
            'DeviceType'    : TelescopeMetadata.DeviceType,
            'DeviceNumber'  : 0,
            'UniqueID'      : TelescopeMetadata.DeviceID
            },
            {
            'DeviceName'    : RotatorMetadata.Name,
            'DeviceType'    : RotatorMetadata.DeviceType,
            'DeviceNumber'  : 0,
            'UniqueID'      : RotatorMetadata.DeviceID
            }        ]
        resp.text = await PropertyResponse(confarray, req)

import socket
import json
import asyncio
import falcon
from typing import List
import psutil


class discoverdevices():
    async def on_get(self, req: falcon.Request, resp: falcon.Response):
        """
        GET /api/discover
        Returns a JSON list of discovered Alpaca devices as ["hostname:port"]
        """
        devices = await discover_alpaca_devices_async()
        resp.status = falcon.HTTP_200
        resp.media = devices

def get_ipv4_interfaces():
    interfaces = []
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if (
                addr.family == socket.AF_INET
                and not addr.address.startswith("127.")
                and not addr.address.startswith("169.254.")
            ):
                interfaces.append(addr.address)
    return interfaces

async def discover_alpaca_devices_async(timeout: float = 2.0) -> List[str]:
    """
    Asynchronously discovers Alpaca devices using UDP multicast.
    Returns a list of "hostname:port" strings.
    """
    MCAST_GRP = '255.255.255.255'
    MCAST_PORT = 32227
    DISCOVERY_MSG = "alpacadiscovery1".encode('utf-8')

    loop = asyncio.get_running_loop()
    discovered = set()
    interfaces = get_ipv4_interfaces()
    print(f"Interfaces: {interfaces}")

    async def send_and_receive(iface_ip):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setblocking(False)
            sock.bind((iface_ip, 0))
            await loop.sock_sendto(sock, DISCOVERY_MSG, (MCAST_GRP, MCAST_PORT))
            end_time = loop.time() + timeout
            while loop.time() < end_time:
                try:
                    data, addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 1024), timeout=0.2)
                    response = json.loads(data.decode('utf-8'))
                    host = response.get("Address") or response.get("RemoteAddress") or addr[0]
                    port = response.get("Port") or response.get("AlpacaPort") or 11111
                    discovered.add(f"{host}:{port}")
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"[{iface_ip}] Error: {e}")
        finally:
            sock.close()

    await asyncio.gather(*(send_and_receive(ip) for ip in interfaces))
    return sorted(discovered)
