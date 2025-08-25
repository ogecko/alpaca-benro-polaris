# -*- coding: utf-8 -*-
#
# -----------------------------------------------------------------------------
# stellarium.py - Stellarium telescope control protocol
#
# This module allows the following applications to use Benro Polaris
# 1. Stellarium (https://stellarium.org/) 
#   Using the Binary Protocol. Useful if you run on MacOS and cant use ASCOM.
#   Limited Support: GOTO only.
#
# 2. Stellarium PLUS (https://stellarium-labs.com/stellarium-mobile-plus/)
#   Using the SynScan Protocol. Useful for Android and Apple mobile devices.
#   Limited Support: GOTO, Move, Sync, Get Precise RA/Dec, Get Tracking State
#                    Sync Location, Sync Time (read only)
# 
# 3. Other SynScan applications. Possible but untested. 
#   If Benro adds the ability to perform Slow Moves, while sidereal tracking
#   is enabled, without the backlash dance, this could potentially  
#   be used for guiding.
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
import time
from config import Config
from shr import DeviceMetadata, LifecycleController
from datetime import datetime
from shr import deg2dms,hr2hms,rad2deg,rad2hr,hr2rad,deg2rad,bytes2hexascii
import ephem
import math
from logging import Logger

##########################################
####### Stellarium/SynScan Support #######
##########################################

#____________Unit Conversions_____________

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
    result_ascii = f"{hour:02}:{minute:02}:{second:02} {month:02}-{day:02}-20{year:02} TZ:{offset} DST:{is_dst}"
    return result, result_ascii

def HQRSTUVWX2datetime(data):
    hour = data[1]
    minute = data[2]
    second = data[3]
    month = data[4]
    day = data[5]
    year = data[6] % 100                    # Get last two digits of the year
    is_dst = data[8]
    offset = data[7]                # Offset in hours from GMT
    if offset >= 256:
        offset = -(offset - 256)
    result_ascii = f"{hour:02}:{minute:02}:{second:02} {month:02}-{day:02}-20{year:02} TZ:{offset} DST:{is_dst}"
    return result_ascii

def WABCDEGFGH2latlon(data):
    # Extract values from byte array
    A = data[1]
    B = data[2]
    C = data[3]
    D = data[4]
    E = data[5]
    F = data[6]
    G = data[7]
    H = data[8]
    # Convert latitude to decimal degrees
    lat_degrees = A + B / 60.0 + C / 3600.0
    if D == 1:  # South
        lat_degrees = -lat_degrees
    # Convert longitude to decimal degrees
    lon_degrees = E + F / 60.0 + G / 3600.0
    if H == 1:  # West
        lon_degrees = -lon_degrees
    return lat_degrees, lon_degrees

def latlon2ABCDEGFGH(latitude, longitude):
    # Determine the hemisphere for latitude
    if latitude < 0:
        D = 1  # South
        latitude = -latitude
    else:
        D = 0  # North
    # Determine the hemisphere for longitude
    if longitude < 0:
        H = 1  # West
        longitude = -longitude
    else:
        H = 0  # East
    # Convert latitude to degrees, minutes, and seconds
    A = int(latitude)
    B = int((latitude - A) * 60)
    C = int(((latitude - A) * 60 - B) * 60)
    # Convert longitude to degrees, minutes, and seconds
    E = int(longitude)
    F = int((longitude - E) * 60)
    G = int(((longitude - E) * 60 - F) * 60)
    # Create the byte array
    byte_array = bytearray([A, B, C, D, E, F, G, H, 0x23])
    return byte_array


def radec_to_SynScan24bit(ra_hours, dec_degrees):
    j2000_coord = ephem.Equatorial(hr2rad(ra_hours), deg2rad(dec_degrees), epoch=ephem.J2000)
    radec = ephem.Equatorial(j2000_coord, epoch=ephem.now())
    # Convert RA from hours to fraction of a revolution
    ra_fraction = radec.ra / math.pi / 2
    # Convert DEC from degrees to fraction of a revolution
    dec_fraction = radec.dec / math.pi / 2 if radec.dec>=0 else (radec.dec + 2*math.pi) / math.pi / 2
    # Convert fractions to 24-bit hexadecimal values
    ra_hex = int(ra_fraction * 16777216)
    dec_hex = int(dec_fraction * 16777216)
    # Format as 6-character hexadecimal strings
    ra_hex_str = format(ra_hex, '06X')
    dec_hex_str = format(dec_hex, '06X')
    # Create the byte array
    byte_array = f"{ra_hex_str}00,{dec_hex_str}00#".encode('ascii')
    return byte_array

def synScan24bit_to_radec(byte_array):
    # Decode the byte array to a string
    hex_string = byte_array[1:].decode('ascii')
    # Extract the RA and DEC hexadecimal values
    ra_hex_str = hex_string[:6]
    dec_hex_str = hex_string[9:15]
    # Convert the hexadecimal values to integers
    ra_hex = int(ra_hex_str, 16)
    dec_hex = int(dec_hex_str, 16)
    # Convert the integers to fractions of a revolution
    ra_fraction = ra_hex / 16777216.0
    dec_fraction = dec_hex / 16777216.0
    # Convert the fractions J2000 ra dec
    now_coord = ephem.Equatorial(ra_fraction*math.pi*2, dec_fraction*math.pi*2, epoch=ephem.now())
    radec = ephem.Equatorial(now_coord, epoch=ephem.J2000)

    return rad2hr(radec.ra), rad2deg(radec.dec)

def bytes2radect(data):
    t = int.from_bytes(data[4:12], byteorder='little')
    ra = int.from_bytes(data[12:16], byteorder='little')
    dec = int.from_bytes(data[16:20], byteorder='little', signed=True)
    ra = (24*ra)/0x100000000
    dec = (90*dec)/0x40000000
    return (ra, dec, t)
    
def radec2bytes(ra, dec, t):
    data = bytearray(26)
    # Message lenght
    data[0] = 26
    # Current time
    data[4:12] = t.to_bytes(8, 'little')
    # Converted RA
    ra = int(ra * 0x100000000 / 24)
    data[12:16] = ra.to_bytes(4, 'little')
    # Converted DEC
    dec = int(dec * 0x40000000 / 90 )
    data[16:20] = dec.to_bytes(4, 'little', signed=True)
    return data


class Stellarium:

    def __init__(self, logger: Logger, reader, writer):
        self.logger = logger
        self.reader = reader
        self.writer = writer
        self.stellarium_binary_protocol = True          # Assume Binary unless Ka received in first 5 seconds

    #____________Low Level Comms_____________
    async def stellarium_send_msg(self, msg, ispolled=False):
        if (not ispolled and Config.log_synscan_protocol) or (ispolled and Config.log_synscan_polling):
            self.logger.info(f"->> Stellarium: send_msg: {bytes2hexascii(msg)}")
        self.writer.write(msg)
        await self.writer.drain()

    #____________Stellarium/SynScan Protocol_____________
    # SynScan Protocol (https://inter-static.skywatcher.com/downloads/synscanserialcommunicationprotocol_version33.pdf)
    # Stellarium Binary Protocol
    async def process_protocol(self, data):

        # hex/ascii dump of message recieved
        ispolled = data[0]==0x4c or data[0]==0x65 or data[0]==0x4a
        if (not ispolled and Config.log_synscan_protocol) or (ispolled and Config.log_synscan_polling):
            self.logger.info(f"<<- Stellarium: recv_msg: {bytes2hexascii(data)}")

        # SynSCAN Echo Command 'K',x | Reply x, "#"
        if data[0]==0x4b:               
            msg = bytearray([data[1],ord('#')])
            telescope.polaris.radec_sync_reset()
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan ECHO Command 'K{chr(data[1])}' | Reset SyncOffset to (RA 0 Dec 0)")
            self.stellarium_binary_protocol = False
            await self.stellarium_send_msg(msg)

        # SynSCAN Get Slewing state 'L' | Reply “0#" or "1#"
        elif data[0]==0x4c: 
            if Config.log_synscan_polling:              
                self.logger.info(f"<<- Stellarium: SynScan Get SLEWING state 'L' | {telescope.polaris.slewing}")
            msg = b'1#' if telescope.polaris.gotoing else b'0#'
            await self.stellarium_send_msg(msg, ispolled=True)

        # SynSCAN Get Tracking state 't' | Reply 0 = Tracking off, 1 = Alt/Az tracking, 2 = Equatorial tracking, 3 = PEC mode (Sidereal + PEC)
        elif data[0]==0x74: 
            if Config.log_synscan_polling:              
                self.logger.info(f"<<- Stellarium: SynScan Get TRACKING state 't' | {telescope.polaris.tracking}")
            msg = bytearray([2,ord('#')]) if telescope.polaris.tracking else bytearray([0,ord('#')])
            await self.stellarium_send_msg(msg, ispolled=True)

        # SynSCAN Set Tracking state 'T',m | Where m=0 Off, m=1 Alt/Az, m=2 Equitorial, m=3 Sidereal+PEC mode
        elif data[0]==0x54: 
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan Set Tracking 'T'")
            new_state = True if data[1]==0x02 or data[1]==0x03 else False
            telescope.polaris.send_cmd_change_tracking_state(new_state)
            msg = b'#'
            await self.stellarium_send_msg(msg)

        # SynSCAN Is Alignment Complete 'J' | Reply 1 = Aligned
        elif data[0]==0x4a: 
            if Config.log_synscan_polling:              
                self.logger.info(f"<<- Stellarium: SynScan Is Alignment Complete 'J'")
            msg = bytearray([1, ord('#')]) if telescope.polaris.connected else bytearray([0, ord('#')])
            await self.stellarium_send_msg(msg, ispolled=True)

        # SynSCAN Cancel GOTO 'M' | Reply “#"
        elif data[0]==0x4d:               
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan Cancel GOTO 'M'")
            await telescope.polaris.send_cmd_goto_abort()
            msg = b'#'
            await self.stellarium_send_msg(msg)

        # SynSCAN Fixed Rate Move Azm Command 'P':02:10:25:Rate:00:00:00
        elif data[0]==0x50 and data[1]==0x02:
            rate = data[4]
            if rate < 0 or rate > telescope.polaris.axisrates[0]['Maximum'] or math.isnan(rate):
                self.logger.error(f"<<- Stellarium: SynScan Move Rate invalid {bytes2hexascii(data)}")
            else:
                if data[2]==0x10 and data[3]==0x24:
                    if Config.log_synscan_protocol:
                        self.logger.info(f"<<- Stellarium: SynScan Move Azm +ve 'P': Rate {rate}")
                    await telescope.polaris.move_axis(0, rate)
                if data[2]==0x10 and data[3]==0x25:
                    if Config.log_synscan_protocol:
                        self.logger.info(f"<<- Stellarium: SynScan Move Azm -ve 'P': Rate {rate}")
                    await telescope.polaris.move_axis(0, -rate)
                if data[2]==0x11 and data[3]==0x24:
                    if Config.log_synscan_protocol:
                        self.logger.info(f"<<- Stellarium: SynScan Move Alt +ve 'P': Rate {rate}")
                    await telescope.polaris.move_axis(1, rate)
                if data[2]==0x11 and data[3]==0x25:
                    if Config.log_synscan_protocol:
                        self.logger.info(f"<<- Stellarium: SynScan Move Alt -ve 'P': Rate {rate}")
                    await telescope.polaris.move_axis(1, -rate)
            msg = b'#'
            await self.stellarium_send_msg(msg)

        # SynSCAN Get Version Command 'V' | Reply 6 decimals in ascii,"#"
        elif data[0]==0x56:
            version = DeviceMetadata.VersionSynScan               
            if Config.log_synscan_protocol:
               self.logger.info(f"<<- Stellarium: SynScan Get VERSION Command 'V' | {version}")
            msg = bytearray(ord(c) for c in version)
            await self.stellarium_send_msg(msg)

        # SynSCAN Get precise RA/DEC 'e' | Reply “34AB0500,12CE0500#” 
        elif data[0]==0x65:               
            await asyncio.sleep(0.1)            # dont let Stellarium PLUS get too carried away
            if Config.log_synscan_polling:              
                self.logger.info(f"<<- Stellarium: SynScan Get RA/DEC Command 'e'")
            msg = radec_to_SynScan24bit(telescope.polaris.rightascension, telescope.polaris.declination)
            await self.stellarium_send_msg(msg, ispolled=True)

        # SynSCAN GOTO 'r34AB0500,12CE0500', | Reply “#"
        elif data[0]==0x72:               
            ra, dec = synScan24bit_to_radec(data)
            if ra < 0 or ra > 24 or math.isnan(ra):
                self.logger.error(f"<<- Stellarium: SynScan GOTO RA invalid {bytes2hexascii(data)}")
            elif dec < -90 or dec > 90 or math.isnan(dec):
                self.logger.error(f"<<- Stellarium: SynScan GOTO Dec invalid {bytes2hexascii(data)}")
            else:
                if Config.log_synscan_protocol:
                    self.logger.info(f"<<- Stellarium: SynScan GOTO Ra: {hr2hms(ra)} Dec: {deg2dms(dec)}")
                if telescope.polaris.connected:
                    await telescope.polaris.SlewToCoordinates(ra, dec, isasync=True)
            msg = b'#'
            await self.stellarium_send_msg(msg)

        # SynSCAN SYNC 's34AB0500,12CE0500', | Reply “#"
        elif data[0]==0x73:               
            ra, dec = synScan24bit_to_radec(data)
            if ra < 0 or ra > 24 or math.isnan(ra):
                self.logger.error(f"<<- Stellarium: SynScan SYNC RA invalid {bytes2hexascii(data)}")
            elif dec < -90 or dec > 90 or math.isnan(dec):
                self.logger.error(f"<<- Stellarium: SynScan SYNC Dec invalid {bytes2hexascii(data)}")
            else:
                if Config.log_synscan_protocol:
                    self.logger.info(f"<<- Stellarium: SynScan SYNC Ra: {ra} Dec: {dec}")
                if telescope.polaris.connected:
                    await telescope.polaris.radec_ascom_sync(ra, dec)
            msg = b'#'
            await self.stellarium_send_msg(msg)

        # SynSCAN Get TIME 'h', | Reply “QRSTUVWX#" where Q hr, R min, S sec, T Month, U day, V year, W GMT offset, X DST
        elif data[0]==0x68:               
            msg, msg_ascii = datetime2QRSTUVWX(datetime.now())
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan Get TIME h | {msg_ascii}")
            await self.stellarium_send_msg(msg)

        # SynSCAN Set TIME 'HQRSTUVWX', | Reply “#" where Q hr, R min, S sec, T Month, U day, V year, W GMT offset, X DST
        elif data[0]==0x48:
            msg_ascii = HQRSTUVWX2datetime(data)               
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan Set TIME H | {msg_ascii}")
            # Mot Implemented
            msg = b'#'
            await self.stellarium_send_msg(msg)

        # SynSCAN Get LOCATION 'w', | Reply “ABCDEFGH#" where 
        elif data[0]==0x77:
            lat = telescope.polaris.sitelatitude
            lon = telescope.polaris.sitelongitude          
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan Get LOCATION w | Lat: {lat:0.9} Lon: {lon:0.9}")
            msg = latlon2ABCDEGFGH(lat, lon)
            await self.stellarium_send_msg(msg)

        # SynSCAN Set LOCATION 'WABCDEFGH', | Reply “#" where 
        elif data[0]==0x57:               
            lat, lon = WABCDEGFGH2latlon(data)
            if lon < -180 or lon > 180 or math.isnan(lon):
                self.logger.error(f"<<- Stellarium: SynScan SYNC Lon invalid {bytes2hexascii(data)}")
            elif lat < -90 or lat > 90 or math.isnan(lat):
                self.logger.error(f"<<- Stellarium: SynScan SYNC Lat invalid {bytes2hexascii(data)}")
            else:
                telescope.polaris.sitelatitude = lat
                telescope.polaris.sitelongitude = lon         
                if Config.log_synscan_protocol:
                    self.logger.info(f"<<- Stellarium: SynScan Set LOCATION W | Lat: {lat:0.9} Lon: {lon:0.9}")
            msg = b'#'
            await self.stellarium_send_msg(msg)

        # Stellarium Desktop Binary Goto Command 
        elif data[0]==0x14:               
            (ra, dec, t) = bytes2radect(data)
            if ra < 0 or ra > 24 or math.isnan(ra):
                self.logger.error(f"<<- Stellarium: Binary GOTO RA invalid {bytes2hexascii(data)}")
            elif dec < -90 or dec > 90 or math.isnan(dec):
                self.logger.error(f"<<- Stellarium: Binary GOTO Dec invalid {bytes2hexascii(data)}")
            else:
                if Config.log_synscan_protocol:
                    self.logger.info(f"<<- Stellarium: Binary GOTO command Ra={ra} Dec={dec} t={t}")
                self.stellarium_binary_protocol = True
                if telescope.polaris.connected:
                    await telescope.polaris.SlewToCoordinates(ra, dec, isasync=True)

        else:
            self.logger.error(f"<<- Stellarium: Unknown Command: {bytes2hexascii(data)}")

    #____________Stellarium Pos Updates_____________
    # Background Loop to send position updates every 500ms for the Binary Protocol
    async def every_500ms_send_position_update(self):
        await asyncio.sleep(5)      # wait 5 seconds for first SynScan Ka protocol to turn off updates
        while True:
            try:
                if self.stellarium_binary_protocol:
                    # Current time
                    t = int(datetime.now().timestamp())
                    # current (RA, Dec)
                    ra = telescope.polaris.rightascension
                    dec = telescope.polaris.declination
                    data = radec2bytes(ra, dec, t)
                    await self.stellarium_send_msg(data, ispolled = True)
                await asyncio.sleep(0.5)
            except Exception as e:
                self.logger.error(f"==ERROR== Network connection to Stellarium lost from Position Updates. {e}")
                await asyncio.sleep(5)
                break


    #____________Stellarium Client_____________
    # Main Stellarium Loop for protocol reading and handling 
    async def client(self):
        while True:
            try: 
                data = await self.reader.read(256)
                if not data:
                    break
                await self.process_protocol(data)
                await asyncio.sleep(0.25)                # slow down Stellarium from polling too quickly and overloading this loop
            except Exception as e:
                self.logger.error(f"==ERROR== Network connection to Stellarium lost from Client. {e}")
                await asyncio.sleep(5)
                break

# Called once for every client connection
async def stellarium_handler(logger, reader, writer):
    # Create a stellarium object to hold all state info about the connection
    stellarium = Stellarium(logger, reader, writer)       

    # Create a background task to send position updates whenever its binary protocol
    asyncio.create_task(stellarium.every_500ms_send_position_update())

    # Perform the main Stellarium protocol reading and handling
    await stellarium.client()


# Main entry for Stellarium
async def synscan_api(logger, lifecycle: LifecycleController):
    if not Config.enable_synscan:
        return

    host = Config.stellarium_synscan_ip_address
    port = Config.stellarium_synscan_port
    logger.info(f"==STARTUP== Serving Stellarium/SynSCAN API on {host}:{port}")

    try:
        server = await asyncio.start_server(
            lambda reader, writer: stellarium_handler(logger, reader, writer),
            host,
            port
        )

        async with server:
            await lifecycle.wait_for_event()
    except asyncio.CancelledError:
        logger.info("==CANCELLED== SynSCAN API cancel received.")
    except Exception as e:
        logger.exception(f"==EXCEPTION== SynSCAN API unhandled exception: {e}")
    finally:
        logger.info("==SHUTDOWN== SynSCAN API shutting down.")
        server.close()
        await server.wait_closed()


