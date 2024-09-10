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
from config import Config
from shr import DeviceMetadata
from datetime import datetime
import time

####### Stellarium

# Convert Datetime to “QRSTUVWX#" where Q hr, R min, S sec, T Month, U day, V year, W GMT offset, X DST
def datetime2QRSTUVWX(dt):
    hour = dt.hour
    minute = dt.minute
    second = dt.second
    month = dt.month
    day = dt.day
    year = dt.year % 100                    # Get last two digits of the year
    is_dst = time.localtime().tm_isdst
    offset = -time.timezone // 3600         # Offset in hours from GMT
    if offset < 0:
        offset = 256 + offset
    result = bytearray([hour,minute,second,month,day,year,offset,is_dst,0x23])
    return result

def radec2SynScan24bit(ra_hours, dec_degrees):
    # Convert RA from hours to fraction of a revolution
    ra_fraction = ra_hours / 24.0
    # Convert DEC from degrees to fraction of a revolution
    dec_fraction = dec_degrees / 360.0 if dec_degrees>=0 else (dec_degrees + 360.0) / 360.0
    # Convert fractions to 24-bit hexadecimal values
    ra_hex = int(ra_fraction * 16777216)
    dec_hex = int(dec_fraction * 16777216)
    # Format as 6-character hexadecimal strings
    ra_hex_str = format(ra_hex, '06X')
    dec_hex_str = format(dec_hex, '06X')
    # Create the byte array
    byte_array = f"{ra_hex_str}00,{dec_hex_str}00#".encode('ascii')
    return byte_array

async def stellarium_send_msg(logger, writer, msg, ispolled=False):
    if Config.log_stellarium_protocol and not(ispolled and Config.supress_stellarium_polling_msgs):
        logger.info(f"->> Stellarium: send_msg {msg}")
    writer.write(msg)
    await writer.drain()


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
        if Config.log_stellarium_protocol:
            logger.info(f"<<- Stellarium: recv_msg {':'.join(('0'+hex(x)[2:])[-2:] for x in data)}")

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

        # SynSCAN Echo Command 'K',x | Reply x, "#"
        if data[0]==0x4b:               
            logger.info(f"<<- Stellarium: ECHO Command 'E{chr(data[1])}'")
            msg = bytearray([data[1],ord('#')])
            await stellarium_send_msg(logger, writer, msg)

        # SynSCAN Get Slewing state 'L' | Reply “0" or "1"
        elif data[0]==0x4c: 
            if not Config.supress_stellarium_polling_msgs:              
                logger.info(f"<<- Stellarium: Get SLEWING state 'L'")
            msg = b'1' if telescope.polaris.slewing else b'0'
            await stellarium_send_msg(logger, writer, msg, ispolled=True)
    
        # SynSCAN Cancel GOTO 'M' | Reply “#"
        elif data[0]==0x4d:               
            logger.info(f"<<- Stellarium: Cancel GOTO 'M'")
            msg = b'#'
            await stellarium_send_msg(logger, writer, msg)
    
        # SynSCAN Fixed Rate Move Azm Command 'P':02:10:25:Rate:00:00:00
        elif data[0]==0x50 and data[1]==0x02:
            if data[2]==0x10 and data[3]==0x24:
                logger.info(f"<<- Stellarium: Move Azm +ve 'P': Rate {data[4]}")
            if data[2]==0x10 and data[3]==0x25:
                logger.info(f"<<- Stellarium: Move Azm -ve 'P': Rate {data[4]}")
            if data[2]==0x11 and data[3]==0x24:
                logger.info(f"<<- Stellarium: Move Alt +ve 'P': Rate {data[4]}")
            if data[2]==0x11 and data[3]==0x25:
                logger.info(f"<<- Stellarium: Move Alt -ve 'P': Rate {data[4]}")
            msg = b'#'
            await stellarium_send_msg(logger, writer, msg)

        # SynSCAN Get Version Command 'V' | Reply 6 decimals in ascii,"#"
        elif data[0]==0x56:               
            logger.info(f"<<- Stellarium: Get VERSION Command 'V'")
            msg = bytearray(ord(c) for c in DeviceMetadata.Version)
            await stellarium_send_msg(logger, writer, msg)

        # SynSCAN Get precise RA/DEC 'e' | Reply “34AB0500,12CE0500#” 
        elif data[0]==0x65:               
            if not Config.supress_stellarium_polling_msgs:              
                logger.info(f"<<- Stellarium: Get RA/DEC Command 'e'")
            msg = radec2SynScan24bit(telescope.polaris.rightascension, telescope.polaris.declination)
            await stellarium_send_msg(logger, writer, msg, ispolled=True)
    
        # SynSCAN GOTO 'r34AB0500,12CE0500', | Reply “#"
        elif data[0]==0x72:               
            logger.info(f"<<- Stellarium: GOTO rXXXXXXXX,XXXXXXXX")
            msg = b'#'
            await stellarium_send_msg(logger, writer, msg)

        # SynSCAN Get TIME 'h', | Reply “QRSTUVWX#" where Q hr, R min, S sec, T Month, U day, V year, W GMT offset, X DST
        elif data[0]==0x68:               
            logger.info(f"<<- Stellarium: Get TIME h")
            msg = datetime2QRSTUVWX(datetime.now())
            await stellarium_send_msg(logger, writer, msg)

        # SynSCAN Set TIME 'HQRSTUVWX', | Reply “#" where Q hr, R min, S sec, T Month, U day, V year, W GMT offset, X DST
        elif data[0]==0x48:               
            logger.info(f"<<- Stellarium: Set TIME H: {data}")
            # Mot Implemented
            msg = b'#'
            await stellarium_send_msg(logger, writer, msg)

        # SynSCAN Get LOCATION 'w', | Reply “ABCDEFGH#" where 
        elif data[0]==0x77:               
            logger.info(f"<<- Stellarium: Get LOCATION w")
            msg = b'#'
            await stellarium_send_msg(logger, writer, msg)

        # SynSCAN Set LOCATION 'WABCDEFGH', | Reply “#" where 
        elif data[0]==0x57:               
            logger.info(f"<<- Stellarium: Set LOCATION W")
            msg = b'#'
            await stellarium_send_msg(logger, writer, msg)

        # Stellarium Binary Goto Command 
        elif data[0]==0x14:               
            (rightascension, declination) = decode_stellarium_packet(logger, data)
            if telescope.polaris.connected:
                await telescope.polaris.SlewToCoordinates(rightascension, declination, isasync=True)

    
async def stellarium_telescope(logger, telescope_ip_address, telescope_port):    
    logger.info(f"==STARTUP== Serving Stellarium Telescope on {telescope_ip_address}:{telescope_port}")

    stellarium_server = await asyncio.start_server(lambda reader, writer: stellarium_handler(logger, reader, writer), 
                                                   telescope_ip_address, telescope_port)

