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
# -----------------------------------------------------------------------------
# MIT License
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

def datetime2QRSTUVWX(dt):
    hour = dt.hour
    minute = dt.minute
    second = dt.second
    month = dt.month
    day = dt.day
    year = dt.year % 100
    is_dst = time.localtime().tm_isdst
    offset = -time.timezone // 3600
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
    year = data[6] % 100
    is_dst = data[8]
    offset = data[7]
    if offset >= 256:
        offset = -(offset - 256)
    result_ascii = f"{hour:02}:{minute:02}:{second:02} {month:02}-{day:02}-20{year:02} TZ:{offset} DST:{is_dst}"
    return result_ascii

def WABCDEGFGH2latlon(data):
    A = data[1]; B = data[2]; C = data[3]; D = data[4]
    E = data[5]; F = data[6]; G = data[7]; H = data[8]
    lat_degrees = A + B / 60.0 + C / 3600.0
    if D == 1:
        lat_degrees = -lat_degrees
    lon_degrees = E + F / 60.0 + G / 3600.0
    if H == 1:
        lon_degrees = -lon_degrees
    return lat_degrees, lon_degrees

def latlon2ABCDEGFGH(latitude, longitude):
    D = 0; H = 0
    if latitude < 0:
        D = 1; latitude = -latitude
    if longitude < 0:
        H = 1; longitude = -longitude
    A = int(latitude);  B = int((latitude - A) * 60);  C = int(((latitude - A) * 60 - B) * 60)
    E = int(longitude); F = int((longitude - E) * 60); G = int(((longitude - E) * 60 - F) * 60)
    return bytearray([A, B, C, D, E, F, G, H, 0x23])


def radec_to_SynScan24bit(ra_hours, dec_degrees):
    jNow_coord = ephem.Equatorial(hr2rad(ra_hours), deg2rad(dec_degrees), epoch=ephem.now())
    radec = ephem.Equatorial(jNow_coord, epoch=ephem.J2000)
    ra_fraction = radec.ra / math.pi / 2
    dec_fraction = radec.dec / math.pi / 2 if radec.dec >= 0 else (radec.dec + 2*math.pi) / math.pi / 2
    ra_hex  = int(ra_fraction  * 16777216)
    dec_hex = int(dec_fraction * 16777216)
    return f"{ra_hex:06X}00,{dec_hex:06X}00#".encode('ascii')

def synScan24bit_to_radec(byte_array):
    hex_string = byte_array[1:].decode('ascii')
    ra_hex  = int(hex_string[:6],  16)
    dec_hex = int(hex_string[9:15], 16)
    ra_fraction  = ra_hex  / 16777216.0
    dec_fraction = dec_hex / 16777216.0
    J2000_coord = ephem.Equatorial(ra_fraction*math.pi*2, dec_fraction*math.pi*2, epoch=ephem.J2000)
    radec = ephem.Equatorial(J2000_coord, epoch=ephem.now())
    return rad2hr(radec.ra), rad2deg(radec.dec)

def bytes2radect(data):
    t   = int.from_bytes(data[4:12], byteorder='little')
    ra  = int.from_bytes(data[12:16], byteorder='little')
    dec = int.from_bytes(data[16:20], byteorder='little', signed=True)
    ra  = (24 * ra)  / 0x100000000
    dec = (90 * dec) / 0x40000000
    return (ra, dec, t)

def radec2bytes(ra, dec, t):
    data = bytearray(26)
    data[0] = 26
    data[4:12] = t.to_bytes(8, 'little')
    data[12:16] = int(ra  * 0x100000000 / 24).to_bytes(4, 'little')
    data[16:20] = int(dec * 0x40000000  / 90).to_bytes(4, 'little', signed=True)
    return data


# ---------------------------------------------------------------------------
# Minimum expected data lengths per command byte.
# Used to guard against short/truncated messages before indexing into data[].
# ---------------------------------------------------------------------------
_MIN_DATA_LEN = {
    0x4b: 2,   # K  echo
    0x4c: 1,   # L  get slewing
    0x74: 1,   # t  get tracking
    0x54: 2,   # T  set tracking
    0x4a: 1,   # J  alignment complete
    0x4d: 1,   # M  cancel goto
    0x50: 5,   # P  fixed rate move
    0x56: 1,   # V  get version
    0x65: 1,   # e  get RA/DEC
    0x72: 16,  # r  goto (SynScan 24-bit)
    0x73: 16,  # s  sync (SynScan 24-bit)
    0x68: 1,   # h  get time
    0x48: 9,   # H  set time
    0x77: 1,   # w  get location
    0x57: 9,   # W  set location
    0x14: 20,  # Binary goto
}


class Stellarium:

    def __init__(self, logger: Logger, reader, writer, stop_event: asyncio.Event):
        self.logger = logger
        self.reader = reader
        self.writer = writer
        self.stop_event = stop_event                    # FIX 1: shared shutdown signal
        self.stellarium_binary_protocol = True

    # __________ Low Level Comms __________

    async def stellarium_send_msg(self, msg, ispolled=False):
        """Send a message to Stellarium. Raises OSError if the connection is lost."""
        if (not ispolled and Config.log_synscan_protocol) or (ispolled and Config.log_synscan_polling):
            self.logger.info(f"->> Stellarium: send_msg: {bytes2hexascii(msg)}")
        self.writer.write(msg)
        await self.writer.drain()   # FIX 2: drain can raise; callers now catch OSError

    # __________ Stellarium/SynScan Protocol __________

    async def process_protocol(self, data):
        """Dispatch a received message to the appropriate handler.

        Guards against truncated packets before any index access.
        """
        if not data:
            return

        cmd = data[0]
        ispolled = cmd in (0x4c, 0x65, 0x4a)

        if (not ispolled and Config.log_synscan_protocol) or (ispolled and Config.log_synscan_polling):
            self.logger.info(f"<<- Stellarium: recv_msg: {bytes2hexascii(data)}")

        # FIX 2: Guard truncated packets before indexing
        min_len = _MIN_DATA_LEN.get(cmd)
        if min_len is not None and len(data) < min_len:
            self.logger.error(
                f"<<- Stellarium: Truncated packet for cmd 0x{cmd:02X}: "
                f"got {len(data)} bytes, need {min_len}: {bytes2hexascii(data)}"
            )
            return

        # SynSCAN Echo Command 'K',x | Reply x, "#"
        if cmd == 0x4b:
            msg = bytearray([data[1], ord('#')])
            telescope.polaris.radec_sync_reset()
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan ECHO 'K{chr(data[1])}' | Reset SyncOffset")
            self.stellarium_binary_protocol = False
            await self.stellarium_send_msg(msg)

        # SynSCAN Get Slewing state 'L' | Reply "0#" or "1#"
        elif cmd == 0x4c:
            if Config.log_synscan_polling:
                self.logger.info(f"<<- Stellarium: SynScan Get SLEWING 'L' | {telescope.polaris.slewing}")
            msg = b'1#' if telescope.polaris.gotoing else b'0#'
            await self.stellarium_send_msg(msg, ispolled=True)

        # SynSCAN Get Tracking state 't'
        elif cmd == 0x74:
            if Config.log_synscan_polling:
                self.logger.info(f"<<- Stellarium: SynScan Get TRACKING 't' | {telescope.polaris.tracking}")
            msg = bytearray([2, ord('#')]) if telescope.polaris.tracking else bytearray([0, ord('#')])
            await self.stellarium_send_msg(msg, ispolled=True)

        # SynSCAN Set Tracking state 'T',m
        elif cmd == 0x54:
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan Set Tracking 'T'")
            new_state = data[1] in (0x02, 0x03)
            telescope.polaris.send_cmd_change_tracking_state(new_state)
            await self.stellarium_send_msg(b'#')

        # SynSCAN Is Alignment Complete 'J'
        elif cmd == 0x4a:
            if Config.log_synscan_polling:
                self.logger.info(f"<<- Stellarium: SynScan Is Alignment Complete 'J'")
            msg = bytearray([1, ord('#')]) if telescope.polaris.connected else bytearray([0, ord('#')])
            await self.stellarium_send_msg(msg, ispolled=True)

        # SynSCAN Cancel GOTO 'M'
        elif cmd == 0x4d:
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan Cancel GOTO 'M'")
            await telescope.polaris.send_cmd_goto_abort()
            await self.stellarium_send_msg(b'#')

        # SynSCAN Fixed Rate Move 'P'
        elif cmd == 0x50 and data[1] == 0x02:
            rate = data[4]
            if rate < 0 or rate > telescope.polaris.axisrates[0]['Maximum'] or math.isnan(rate):
                self.logger.error(f"<<- Stellarium: SynScan Move Rate invalid {bytes2hexascii(data)}")
            else:
                axis_dir = {
                    (0x10, 0x24): ( 0,  rate),
                    (0x10, 0x25): ( 0, -rate),
                    (0x11, 0x24): ( 1,  rate),
                    (0x11, 0x25): ( 1, -rate),
                }
                key = (data[2], data[3])
                if key in axis_dir:
                    axis, signed_rate = axis_dir[key]
                    if Config.log_synscan_protocol:
                        self.logger.info(f"<<- Stellarium: SynScan Move axis={axis} rate={signed_rate}")
                    await telescope.polaris.move_axis(axis, signed_rate)
            await self.stellarium_send_msg(b'#')

        # SynSCAN Get Version 'V'
        elif cmd == 0x56:
            version = DeviceMetadata.VersionSynScan
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan Get VERSION 'V' | {version}")
            await self.stellarium_send_msg(bytearray(ord(c) for c in version))

        # SynSCAN Get precise RA/DEC 'e'
        elif cmd == 0x65:
            await asyncio.sleep(0.1)
            if Config.log_synscan_polling:
                self.logger.info(f"<<- Stellarium: SynScan Get RA/DEC 'e'")
            msg = radec_to_SynScan24bit(telescope.polaris.rightascension, telescope.polaris.declination)
            await self.stellarium_send_msg(msg, ispolled=True)

        # SynSCAN GOTO 'r'
        elif cmd == 0x72:
            ra, dec = synScan24bit_to_radec(data)
            if not (0 <= ra <= 24) or math.isnan(ra):
                self.logger.error(f"<<- Stellarium: SynScan GOTO RA invalid {bytes2hexascii(data)}")
            elif not (-90 <= dec <= 90) or math.isnan(dec):
                self.logger.error(f"<<- Stellarium: SynScan GOTO Dec invalid {bytes2hexascii(data)}")
            else:
                if Config.log_synscan_protocol:
                    self.logger.info(f"<<- Stellarium: SynScan GOTO Ra: {hr2hms(ra)} Dec: {deg2dms(dec)}")
                if telescope.polaris.connected:
                    await telescope.polaris.SlewToCoordinates(ra, dec, isasync=True)
            await self.stellarium_send_msg(b'#')

        # SynSCAN SYNC 's'
        elif cmd == 0x73:
            ra, dec = synScan24bit_to_radec(data)
            if not (0 <= ra <= 24) or math.isnan(ra):
                self.logger.error(f"<<- Stellarium: SynScan SYNC RA invalid {bytes2hexascii(data)}")
            elif not (-90 <= dec <= 90) or math.isnan(dec):
                self.logger.error(f"<<- Stellarium: SynScan SYNC Dec invalid {bytes2hexascii(data)}")
            else:
                if Config.log_synscan_protocol:
                    self.logger.info(f"<<- Stellarium: SynScan SYNC Ra: {ra} Dec: {dec}")
                if telescope.polaris.connected:
                    await telescope.polaris.sync_to_radec(ra, dec)
            await self.stellarium_send_msg(b'#')

        # SynSCAN Get TIME 'h'
        elif cmd == 0x68:
            msg, msg_ascii = datetime2QRSTUVWX(datetime.now())
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan Get TIME 'h' | {msg_ascii}")
            await self.stellarium_send_msg(msg)

        # SynSCAN Set TIME 'H' (read-only — we acknowledge but don't apply)
        elif cmd == 0x48:
            msg_ascii = HQRSTUVWX2datetime(data)
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan Set TIME 'H' | {msg_ascii} (not applied)")
            await self.stellarium_send_msg(b'#')

        # SynSCAN Get LOCATION 'w'
        elif cmd == 0x77:
            lat = telescope.polaris.sitelatitude
            lon = telescope.polaris.sitelongitude
            if Config.log_synscan_protocol:
                self.logger.info(f"<<- Stellarium: SynScan Get LOCATION 'w' | Lat: {lat:.6f} Lon: {lon:.6f}")
            await self.stellarium_send_msg(latlon2ABCDEGFGH(lat, lon))

        # SynSCAN Set LOCATION 'W'
        elif cmd == 0x57:
            lat, lon = WABCDEGFGH2latlon(data)
            if not (-180 <= lon <= 180) or math.isnan(lon):
                self.logger.error(f"<<- Stellarium: SynScan Set LOCATION Lon invalid {bytes2hexascii(data)}")
            elif not (-90 <= lat <= 90) or math.isnan(lat):
                self.logger.error(f"<<- Stellarium: SynScan Set LOCATION Lat invalid {bytes2hexascii(data)}")
            else:
                telescope.polaris.sitelatitude  = lat
                telescope.polaris.sitelongitude = lon
                if Config.log_synscan_protocol:
                    self.logger.info(f"<<- Stellarium: SynScan Set LOCATION 'W' | Lat: {lat:.6f} Lon: {lon:.6f}")
            await self.stellarium_send_msg(b'#')

        # Stellarium Desktop Binary GOTO (0x14)
        elif cmd == 0x14:
            ra, dec, t = bytes2radect(data)
            if not (0 <= ra <= 24) or math.isnan(ra):
                self.logger.error(f"<<- Stellarium: Binary GOTO RA invalid {bytes2hexascii(data)}")
            elif not (-90 <= dec <= 90) or math.isnan(dec):
                self.logger.error(f"<<- Stellarium: Binary GOTO Dec invalid {bytes2hexascii(data)}")
            else:
                if Config.log_synscan_protocol:
                    self.logger.info(f"<<- Stellarium: Binary GOTO Ra={ra} Dec={dec} t={t}")
                self.stellarium_binary_protocol = True
                if telescope.polaris.connected:
                    await telescope.polaris.SlewToCoordinates(ra, dec, isasync=True)

        else:
            self.logger.error(f"<<- Stellarium: Unknown Command: {bytes2hexascii(data)}")

    # __________ Stellarium Pos Updates __________

    async def every_500ms_send_position_update(self):
        """Send binary-protocol position updates every 500 ms.

        FIX 1: Respects stop_event so a RESTART shuts this loop down promptly.
        FIX 2: Treats OSError as a clean disconnect; other exceptions are logged
               and then the loop exits, setting stop_event so the client loop
               also terminates rather than continuing on a dead writer.
        """
        # Wait up to 5 s for the SynScan Ka echo to arrive and disable binary mode.
        # FIX 1: Use wait_for so a shutdown during this delay isn't missed.
        try:
            await asyncio.wait_for(self.stop_event.wait(), timeout=5.0)
            return      # stop requested during grace period — exit immediately
        except asyncio.TimeoutError:
            pass        # normal path — grace period elapsed, start sending

        while not self.stop_event.is_set():
            try:
                if self.stellarium_binary_protocol:
                    t   = int(datetime.now().timestamp())
                    ra  = telescope.polaris.rightascension
                    dec = telescope.polaris.declination
                    await self.stellarium_send_msg(radec2bytes(ra, dec, t), ispolled=True)
                await asyncio.sleep(0.5)
            except OSError as e:
                # Remote closed the connection — normal disconnect path
                self.logger.info(f"==INFO== Stellarium position loop: connection closed ({e})")
                self.stop_event.set()   # FIX 2: tell client() to stop too
                break
            except Exception as e:
                self.logger.error(f"==ERROR== Stellarium position loop unexpected error: {e}")
                self.stop_event.set()   # FIX 2: propagate to client loop
                break

    # __________ Stellarium Client __________

    async def client(self):
        """Main receive loop.

        FIX 1: Uses asyncio.wait() to race reader.read() against stop_event so
               a lifecycle RESTART (or position-loop failure) unblocks the read
               immediately without needing Stellarium to close the connection.
        FIX 2: Catches OSError separately from unexpected exceptions so normal
               disconnects don't produce noisy tracebacks.
        """
        while not self.stop_event.is_set():
            try:
                # FIX 1: Race the blocking read against the stop signal.
                read_task = asyncio.ensure_future(self.reader.read(256))
                stop_task = asyncio.ensure_future(self.stop_event.wait())
                done, pending = await asyncio.wait(
                    [read_task, stop_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                # Cancel whichever future didn't finish
                for fut in pending:
                    fut.cancel()
                    try:
                        await fut
                    except (asyncio.CancelledError, Exception):
                        pass

                if stop_task in done:
                    # Shutdown/restart requested — exit cleanly
                    self.logger.info("==INFO== Stellarium client: stop event received, closing.")
                    break

                # read_task finished — check the result
                data = read_task.result()
                if not data:
                    self.logger.info("==INFO== Stellarium client: remote closed connection.")
                    break

                await self.process_protocol(data)
                await asyncio.sleep(0.25)    # slow down Stellarium from polling too quickly, overloading this loop, leading to Win11 going very slow

            except OSError as e:
                # Network error — expected on abrupt disconnect
                self.logger.info(f"==INFO== Stellarium client: connection lost ({e})")
                break
            except Exception as e:
                # Unexpected — log with traceback but keep the loop alive
                self.logger.exception(f"==ERROR== Stellarium client: unexpected error: {e}")
                # Brief back-off before retrying so we don't spin hard on a
                # persistent failure (e.g. a bad telescope.polaris state).
                await asyncio.sleep(1.0)


# Called once for every client connection.
# shutdown_event is a module-local asyncio.Event created by synscan_api and
# shared across all active connections.  It is set only when synscan_api is
# cancelled (global RESTART/SHUTDOWN).  A normal remote disconnect does NOT
# touch it.
async def stellarium_handler(logger, reader, writer, shutdown_event: asyncio.Event):
    peer = writer.get_extra_info('peername', '<unknown>')
    logger.info(f"==INFO== Stellarium: new connection from {peer}")

    stellarium = Stellarium(logger, reader, writer, shutdown_event)
    pos_task = asyncio.create_task(stellarium.every_500ms_send_position_update())

    try:
        await stellarium.client()
    finally:
        # Cancel the position loop.  Do NOT set shutdown_event here — that
        # belongs to synscan_api and must not fire on a normal remote disconnect.
        pos_task.cancel()
        try:
            await pos_task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            writer.close()
            await writer.wait_closed()
        except OSError:
            pass
        logger.info(f"==INFO== Stellarium: connection from {peer} closed.")


# Main entry for Stellarium.
#
# The LifecycleController is referenced only at this boundary — synscan_api
# waits to be cancelled by the lifecycle task manager, exactly like every
# other service in the driver.  Nothing inside this module touches the
# lifecycle directly.
async def synscan_api(logger, lifecycle: LifecycleController):
    if not Config.enable_synscan:
        return

    server = None
    host = Config.stellarium_synscan_ip_address
    port = Config.stellarium_synscan_port
    logger.info(f"==STARTUP== Serving Stellarium/SynSCAN API on {host}:{port}")

    # Module-local shutdown signal, shared with all connection handlers.
    # Set in the finally block so every active read loop exits cleanly
    # when this coroutine is cancelled.
    shutdown_event = asyncio.Event()

    try:
        server = await asyncio.start_server(
            lambda reader, writer: stellarium_handler(logger, reader, writer, shutdown_event),
            host,
            port
        )
        # Do NOT use `async with server` — its __aexit__ calls server.close()
        # and then waits for handlers to finish BEFORE we can set shutdown_event,
        # causing an 8-second deadlock when a connection is open at shutdown time.
        await asyncio.sleep(float('inf'))   # cancelled instantly by lifecycle.shutdown_tasks()

    except asyncio.CancelledError:
        logger.info("==CANCELLED== SynSCAN API cancel received.")
    except Exception as e:
        logger.exception(f"==EXCEPTION== SynSCAN API unhandled exception: {e}")
    finally:
        # Step 1: unblock all active read loops FIRST — they are racing
        #         reader.read() against shutdown_event, so setting it here
        #         causes every handler to exit its loop and call writer.close().
        shutdown_event.set()
        logger.info("==SHUTDOWN== SynSCAN API shutting down.")
        if server is not None:
            # Step 2: stop accepting new connections.
            server.close()
            try:
                # Step 3: wait for all handler coroutines to finish.
                #         Safe now because shutdown_event is already set.
                await server.wait_closed()
            except Exception:
                pass