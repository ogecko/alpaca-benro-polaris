# -*- coding: utf-8 -*-
#
# -----------------------------------------------------------------------------
# stellarium.py - Stellarium telescope control protocol
#
# This module allows to use Stellarium (https://stellarium.org/) to control the
# Benro Polaris
#
# Python Compatibility: Requires Python 3.7 or later
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

import asyncio
import telescope
import config

####### Stellarium

def decode_stellarium_packet(logger, s):
    t = int.from_bytes(s[4:11], byteorder='little')

    ra = int.from_bytes(s[12:16], byteorder='little')
    dec = int.from_bytes(s[16:20], byteorder='little', signed=True)

    ra = (24*ra)/0x100000000
    dec = (90*dec)/0x40000000

    logger.info(f"<<- Stellarium: t={t} ra={ra} dec={dec}")
    
    return (ra, dec)

async def stellarium_handler(logger, reader, writer):
    while True:
        data = await reader.read(256)
        if not data:
            break
        logger.info(f"<<- Stellarium: {':'.join(('0'+hex(x)[2:])[-2:] for x in data)}")

# This module needs to cater for Stellarium PLUS App connections
# Upon initial connection Stellarium PLUS interrogates the port with 3 different protocols
# to try and determine what type of telescope is connected. 
# Current code doesnt respond correctly and assumes only one protocol and misreads the time/RA/DEC as 0,0,0
#
# Attempt 1 - SynScan Protocol (https://inter-static.skywatcher.com/downloads/synscanserialcommunicationprotocol_version33.pdf)
# 2024-09-10T04:37:52.204 INFO <<- Stellarium: 4b:61            ("K", 'a') SkyWatcher Echo command used to check commms
# 2024-09-10T04:37:52.204 INFO <<- Stellarium: t=0 ra=0.0 dec=0.0
# 2024-09-10T04:37:52.215 INFO ->> Polaris: GOTO ASCOM RA: 0.00000000 Dec: 0.00000000
# Attempt 2
# 2024-09-10T04:37:55.709 INFO <<- Stellarium: 23:23            ("#", "#")
# 2024-09-10T04:37:55.709 INFO <<- Stellarium: t=0 ra=0.0 dec=0.0
# 2024-09-10T04:37:55.716 INFO ->> Polaris: GOTO ASCOM RA: 0.00000000 Dec: 0.00000000
# Attempt 3
# 2024-09-10T04:37:59.214 INFO <<- Stellarium: 23:06            ("#", 0x06)
# 2024-09-10T04:37:59.214 INFO <<- Stellarium: t=0 ra=0.0 dec=0.0
# 2024-09-10T04:37:59.218 INFO ->> Polaris: GOTO ASCOM RA: 0.00000000 Dec: 0.00000000
# Hangs up

# Stellarium Desktop App protocol (byes 0-3=cmd 4-11=t, 12-15=RA, 16-19=Dec)
# 2024-09-10T05:25:07.502 INFO <<- Stellarium: 14:00:00:00:  9e:eb:c0:18:bd:21:06:00:  07:77:b8:84:  9f:1c:21:d3
# 2024-09-10T05:25:07.502 INFO <<- Stellarium: t=1725945908095902 ra=12.442553082481027 dec=-63.09936144389212
# 2024-09-10T05:25:07.505 INFO ->> Polaris: GOTO ASCOM RA: 12.44255308 Dec: -63.09936144




        (rightascension, declination) = decode_stellarium_packet(logger, data)
        if telescope.polaris.connected:
            await telescope.polaris.SlewToCoordinates(rightascension, declination, isasync=True)

async def stellarium_telescope(logger, telescope_ip_address, telescope_port):    
    logger.info(f"==STARTUP== Serving Stellarium Telescope on {telescope_ip_address}:{telescope_port}")

    stellarium_server = await asyncio.start_server(lambda reader, writer: stellarium_handler(logger, reader, writer), 
                                                   telescope_ip_address, telescope_port)

