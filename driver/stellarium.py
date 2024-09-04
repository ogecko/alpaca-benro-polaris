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
        (rightascension, declination) = decode_stellarium_packet(logger, data)
        if telescope.polaris.connected:
            await telescope.polaris.SlewToCoordinates(rightascension, declination, isasync=True)

async def stellarium_telescope(logger, polaris_telescope_port):    
    logger.info(f"Stellarium telescope server port={polaris_telescope_port}")

    stellarium_server = await asyncio.start_server(lambda reader, writer: stellarium_handler(logger, reader, writer), 'localhost', polaris_telescope_port)

