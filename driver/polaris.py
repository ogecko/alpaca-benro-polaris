# =================================================================
# POLARIS.PY - Proxy for Benro Polaris device
# =================================================================
#
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# polaris.py - Simulation of a "telescope" mount
#
# This module contains a primary Polaris Class that represents a Benro Polaris and 
# the connection to the Device, including all of its state parameters implied by 
# ASCOM ITelescopeV3.
#
# It provides thread-safe access to read and write its properties.
# It provides functions to perform methods required by ITelescopeV3.
# It provides all the communications functions for asynchronous two 
# way communication with the Benro Polaris Device.
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
# TODO:
# * Implement ASCOM sync
# DONE:
# * Move Slow and Move Fast
# * Park/Unpark (reset axis)
# * retry connecting to polaris if not currently
# * provide proper error messages when ASMCOM connect put (no wifi connect, no ip network, no Astro mode, no Alignment)
# * cater for comms error (lose comms, lose wifi, change mode)
# * error check before using self._writer or self._reader
# * Improve exception handling
# * Add retries for when comms fails to Polaris
# * Current Polaris pointing position shown in Stellarium
# * Slew to target from Stellarium (Telescope Control)
# * Slew to target from Nina (Sky Atlas, Framing, Manual Focus Target)
# * Improve aiming accuracy by allowing sidereal tracking settling time into ra/dec to alt/az calculations
# * Improve aiming accuracy by using a learning algorithm based on past alt/az aiming results
# * Tracking rate set from Nina (Equipment>Mount>Manual Control: Sidereal, Stopped)
# * Telescope Discover/Connect/Disconnect from Nina (Equiment>Mount)
# * Telescope Discover/Connect/Disconnect from Stellarium (Configure Telescopes)
# * Multiple apps connecting to driver concurrently ie (Nina and Stellarium)
# * Site Location Sync from Nina (Options>Equipment>Mount Location Sync)
# * ASCOM Conform Universal TelescopeV3 compliance
# * Calculate current RA/Dec from Polaris Alt/Az updates 
# * allow restart of driver without interrupting existing clients (assume they remain connected)
#
#
#
import math
import datetime
import re
import asyncio
import ephem
from threading import Lock
from logging import Logger
from config import Config
from exceptions import AstroModeError, AstroAlignmentError
from shr import dec2dms, deg2rad, rad2hr, rad2deg, hr2rad, empty_queue

class Polaris:
    """Simulated telescope device that communicates with Polaris Device
    
    Properties and  methods generally follow the Alpaca interface.
    Hopefully you are familiar with Python threading and the need to lock
    shared data items.

    **Mechanical vs Virtual Position**

    In this code 'mech' refers to the raw mechanical position. Note the
    conversions ``_pos_to_mech()`` and ``_mech_to_pos()``. This is where
    the ``Sync()`` offset is applied.

    """
    #
    # Only override __init_()  and run() (pydoc 17.1.2)
    #
    def __init__(self, logger: Logger):
        self._lock = Lock()
        self.name: str = 'device'
        self.logger = logger
        #
        # Polaris device communications state variables
        #
        self._reader = None                         # Stream to receive data from the Polaris device (opened by polaris.client())
        self._writer = None                         # Stream to transmit data to the Polaris device (used by polaris.send_msg())
        self._response_queues = {
            '284': asyncio.Queue(),                 # queue for MODE result
            '519': asyncio.Queue(),                 # queue for GOTO result (2 return msgs per GOTO)
            '531': asyncio.Queue()                  # queue for TRACK result
        }
        self._current_mode = -1                     # Current Mode of the Polaris Device (8 = Astro, 1=Photo, 2=Pano, 3=Focus, 4=Timelapse, 5=Pathlapse, 6=HDR, 7=HolyG 10=Video, )
        self._polaris_msg_re = re.compile(r'^(\d\d\d)@([^#]*)#')
        self._every_50ms_msg_to_send = None         # Fast Move message to send every 50ms
        self._every_50ms_counter = 0                # Fast Move counter, incrementing every 50ms up to 1s
        self._every_50ms_last_timestamp = None      # Fast Move counter, last 1s timestamp
        self._every_50ms_last_alt = None            # Fast Move counter, last 1s polaris altitude
        self._every_50ms_last_az = None             # Fast Move counter, last 1s polaris azimuth
        self._data1_header_timestamp = None       # Timestamp that EXTRACT header was logged. ie start of EXTRACT.
        self._task_exception = None                 # record of any exception from sub tasks
        self._task_errorstr = ''                    # record of any connection issues with polaris (reset at next attempt to reconnect)
        self._task_errorstr_last_attempt = ''       # record of any connection issues with polaris

        #
        # Polaris site/device location variables
        #
        self._sitelatitude: float = float(Config.site_latitude)     # The geodetic(map) latitude (degrees, positive North, WGS84) of the site at which the telescope is located.
        self._sitelongitude: float = float(Config.site_longitude)   # The longitude (degrees, positive East, WGS84) of the site at which the telescope is located.
        self._siteelevation: float = float(Config.site_elevation)   # The elevation above mean sea level (meters) of the site at which the telescope is located
        self._observer = ephem.Observer()                           # Observer object for the telescopes site
        self._observer.pressure = 0                                 # no refraction correction.
        self._observer.epoch = ephem.J2000                          # a moment in time used as a reference point for RA/Dec
        self._observer.lat = dec2dms(self._sitelatitude)            # dms version on lat
        self._observer.long = dec2dms(self._sitelongitude)          # dms version of long
        self._observer.elevation = self._siteelevation              # site elevation
        #
        # Telescope device completion flags
        #
        self._connections = {}                      # Dictionary of client's connection status True/False
        self._connected: bool = False               # Polaris connection status. True if any client is connected. False when all clients have left.
        self._tracking: bool = False                # The state of the telescope's sidereal tracking drive.
        self._sideofpier: int = -1                  # Indicates the pointing state of the mount. Unknown = -1
        self._athome: bool = False                  # True if the telescope is stopped in the Home position. Set only following a FindHome() operation, and reset with any slew operation. This property must be False if the telescope does not support homing.
        self._atpark: bool = False                  # True if the telescope has been put into the parked state by the seee Park() method. Set False by calling the Unpark() method.
        self._slewing: bool = False                 # True if telescope is in the process of moving in response to one of the Goto methods or the MoveAxis(TelescopeAxes, Double) method, False at all other times.
        self._gotoing: bool = False                 # True if telescope is in the process of moving in response to one of the Goto methods, False at all other times.
        self._ispulseguiding: bool = False          # True if a PulseGuide(GuideDirections, Int32) command is in progress, False otherwise
        #
        # Telescope device state variables
        #
        self._altitude: float = 0.0                 # The Altitude above the local horizon of the telescope's current position (degrees, positive up)
        self._azimuth: float = 0.0                  # The Azimuth at the local horizon of the telescope's current position (degrees, North-referenced, positive East/clockwise).
        self._declination: float = 0.0              # The declination (degrees) of the telescope's current equatorial coordinates, in the coordinate system given by the EquatorialSystem property. Reading the property will raise an error if the value is unavailable.
        self._rightascension: float = 0.0           # The right ascension (hours) of the telescope's current equatorial coordinates, in the coordinate system given by the EquatorialSystem property
        self._p_altitude: float = 0.0               # The Altitude of the Polaris
        self._p_azimuth: float = 0.0                # The Azimuth of the Polaris
        self._p_declination: float = 0.0            # The declination (degrees) of the Polaris
        self._p_rightascension: float = 0.0         # The right ascension (hours) of the Polaris
        self._siderealtime: float = 0.0             # The local apparent sidereal time from the telescope's internal clock (hours, sidereal)
        self._aim_altitude: float = 0.0             # The Altitude of the last goto command
        self._aim_azimuth: float = 0.0              # The Azimuth of the last goto command
        self._adj_altitude: float = Config.aiming_adjustment_alt    # The Altitude adjustment to correct the aim based on past goto results
        self._adj_azimuth: float = Config.aiming_adjustment_az      # The Azimuth adjustment to correct the aim based on past goto results
        self._adj_rightascension: float = 0         # The Rightascension adjustment difference between polaris and ascom
        self._adj_declination: float = 0            # The Declination adjustment difference between polaris and ascom
        #
        # Telescope device rates
        #
        self._trackingrate: int = 0                 # Well-known telescope tracking rates. 0 = Sidereal tracking rate (15.041 arcseconds per second).
        self._trackingrates = [0]                   # Returns a collection of supported DriveRates values that describe the permissible values of the TrackingRate property for this telescope type.
        self._declinationrate: float = 0.0          # The declination tracking rate (arcseconds per SI second, default = 0.0)
        self._rightascensionrate: float = 0.0       # The right ascension tracking rate offset from sidereal (seconds per sidereal second, default = 0.0)
        self._guideratedeclination: float = 0.0     # The current Declination movement rate offset for telescope guiding (degrees/sec)
        self._guideraterightascension: float = 0.0  # The current Right Ascension movement rate offset for telescope guiding (degrees/sec)
        #
        # Telescope device settings
        #
        self._alignmentmode: int = 0                # enum for Altitude-Azimuth alignment.
        self._equatorialsystem: int = 2             # Equatorial coordinate system used by this telescope (2 = J2000 equator/equinox. Coordinates of the object at mid-day on 1st January 2000, ICRS reference frame.).
        self._focallength: float = Config.focal_length/1000                       # The telescope's focal length, meters
        self._focalratio: float = Config.focal_ratio                              # The telescope's focal ratio
        self._aperturediameter: float = self._focallength / self._focalratio      # The telescope's effective aperture diameter (meters)
        self._aperturearea: float = math.pi * (self._aperturediameter / 2)**2     # The area of the telescope's aperture, taking into account any obstructions (square meters)
        self._slewsettletime: int = 0               # Specifies a post-slew settling time (sec.).
        self._supportedactions = []                 # Returns the list of custom action names supported by this driver.
        self._targetdeclination: float = None       # The declination (degrees, positive North) for the target of an equatorial slew or sync operation
        self._targetrightascension: float = None    # The right ascension (hours) for the target of an equatorial slew or sync operation
        #
        # Telescope capability constants
        #
        self._canfindhome: bool = False             # True if this telescope is capable of programmed finding its home position (FindHome() method).
        self._canpark: bool = True                  # True if this telescope is capable of programmed parking (Park()method)
        self._canpulseguide: bool = False           # True if this telescope is capable of software-pulsed guiding (via the PulseGuide(GuideDirections, Int32) method)
        self._cansetdeclinationrate: bool = False   # True if the DeclinationRate property can be changed to provide offset tracking in the declination axis.
        self._cansetguiderates: bool = False        # True if the guide rate properties used for PulseGuide(GuideDirections, Int32) can ba adjusted.
        self._cansetpark: bool = False              # True if this telescope is capable of programmed setting of its park position (SetPark() method)
        self._cansetpierside: bool = False          # True if the SideOfPier property can be set, meaning that the mount can be forced to flip.
        self._cansetrightascensionrate: bool = False# True if the RightAscensionRate property can be changed to provide offset tracking in the right ascension axis.
        self._cansettracking: bool = True           # True if the Tracking property can be changed, turning telescope sidereal tracking on and off.
        self._canslew: bool = True                  # True if this telescope is capable of programmed slewing (synchronous or asynchronous) to equatorial coordinates
        self._canslewasync: bool = True             # True if this telescope is capable of programmed asynchronous slewing to equatorial coordinates.
        self._canslewaltaz: bool = True             # True if this telescope is capable of programmed slewing (synchronous or asynchronous) to local horizontal coordinates
        self._canslewaltazasync: bool = True        # True if this telescope is capable of programmed asynchronous slewing to local horizontal coordinates
        self._cansync: bool = True                  # True if this telescope is capable of programmed synching to equatorial coordinates.
        self._cansyncaltaz: bool = False            # True if this telescope is capable of programmed synching to local horizontal coordinates
        self._canunpark: bool = True                # True if this telescope is capable of programmed unparking (Unpark() method).
        self._doesrefraction: bool = False          # True if the telescope or driver applies atmospheric refraction to coordinates.
        #
        # Telescope method constants
        #
        self._axisrates = [{ "Maximum":9, "Minimum":1 }] # Describes a range of rates supported by the MoveAxis(TelescopeAxes, Double) method (degrees/per second)   
        self._axis_slow_slewing = [ 0, 0, 0 ]            # Records the move rate of the primary, seconday and tertiary axis
        self._canmoveaxis = [ True, True, True ]         # True if this telescope can move the requested axis



    ########################################
    # POLARIS COMMUNICATIONS METHODS 
    ########################################

    # Exceptions
    # ConnectionAbortedError [WinError 1236] The network connection was aborted by the local system
    # OSError [error 22][WinError 121] The semaphore timeout period has expired

    # open connection and serve as polaris client
    async def client(self, logger: Logger):
        # background_keepalive = asyncio.create_task(self._every_5s_send_keepalive())
        background_fastmove = asyncio.create_task(self.every_50ms_send_message())
        while True:
            try:
                self._connected = False             # set to true when "Polaris communication init... done"
                self._task_exception = None
                client_reader, client_writer = await asyncio.open_connection(Config.polaris_ip_address, Config.polaris_port)
                self._reader = client_reader
                self._writer = client_writer
                logger.info(f'==STARTUP== Polaris Client on {Config.polaris_ip_address}:{Config.polaris_port}. ')
                init_task = asyncio.create_task(self.polaris_init())
                init_task.add_done_callback(self.task_done)
                await self.read_msgs()

            except ConnectionAbortedError as e:
                self._task_errorstr = f'==STARTUP== The Polaris network connection was aborted.'
                logger.error(self._task_errorstr)
                await asyncio.sleep(5)
                continue

            except OSError as e:
                if hasattr(e, 'winerror'):
                    if e.winerror == 121:
                        self._task_errorstr = f'==STARTUP== Cannot open network connection to Polaris. Connect with Polaris App, then check Wifi connection.'
                        logger.error(self._task_errorstr)
                        await asyncio.sleep(5)
                        continue
                    if e.winerror == 1225:
                        self._task_errorstr = f'==STARTUP== Network connection to Polaris was refused. Connect with Polaris App, then check Wifi connection.'
                        logger.error(self._task_errorstr)
                        await asyncio.sleep(5)
                        continue
                    if e.winerror == 1236:
                        self._task_errorstr = f'==ERROR== Network connection to Polaris lost. Use Polaris App to reconnect.'
                        logger.error(self._task_errorstr)
                        await asyncio.sleep(5)
                        continue

                elif e.errno == 51:
                        self._task_errorstr = f'==STARTUP== Cannot open network connection to Polaris. Connect with Polaris App, then check Wifi connection.'
                        logger.error(self._task_errorstr)
                        await asyncio.sleep(5)
                        continue
                else:
                    raise e

                
            except AstroModeError as e:
                self._task_errorstr = f'==STARTUP== Polaris not in Astro Mode. Use Polaris App to change.'
                logger.error(self._task_errorstr)
                await asyncio.sleep(15)
                continue

            except AstroAlignmentError as e:
                self._task_errorstr = f'==STARTUP== Polaris not Aligned. Use Polaris App to complete alignment.'
                logger.error(self._task_errorstr)
                await asyncio.sleep(15)
                continue

    def task_done(self, task):
        self._task_exception = task.exception()

    def radec2altaz(self, ra, dec, inthefuture=0):
        target = ephem.FixedBody()
        target._ra = hr2rad(ra)
        target._dec = deg2rad(dec)
        target._epoch = ephem.J2000
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        self._observer.date = now + datetime.timedelta(seconds=inthefuture)
        target.compute(self._observer)
        alt = rad2deg(target.alt)
        az = rad2deg(target.az)
        return alt,az

    def altaz2radec(self, alt, az):
        self._observer.date = datetime.datetime.now(tz=datetime.timezone.utc)
        ra_rad, dec_rad = self._observer.radec_of(deg2rad(az), deg2rad(alt))
        ra = rad2hr(ra_rad)  
        dec = rad2deg(dec_rad)
        return ra, dec

    def radec_polaris2ascom(self, p_ra, p_dec):
        a_ra = p_ra + self._adj_rightascension
        a_dec = p_dec + self._adj_declination
        return a_ra, a_dec

    def radec_ascom2polaris(self, a_ra, a_dec):
        p_ra = a_ra - self._adj_rightascension
        p_dec = a_dec - self._adj_declination
        return p_ra, p_dec

    def radec_sync_reset(self):
        self._adj_rightascension = 0
        self._adj_declination = 0
        return

    def radec_sync_ascom(self, a_ra, a_dec):
        self.logger.info(f"->> Polaris: SYNC ASCOM RA {dec2dms(a_ra)} Dec {dec2dms(a_dec)}")
        bad_ra, bad_dec = self.radec_polaris2ascom(self._p_rightascension, self._p_declination)
        offset_ra = a_ra - bad_ra
        offset_dec = a_dec - bad_dec
        self._adj_rightascension = offset_ra
        self._adj_declination = offset_dec
        self._rightascension = a_ra 
        self._declination = a_dec
        self._targetrightascension = a_ra
        self._targetdeclination = a_dec
        a_alt, a_az = self.radec2altaz(a_ra, a_dec)
        self._altitude = a_alt
        self._azimuth = a_az
        return

    async def send_msg(self, msg):
        if Config.log_polaris_protocol:
            self.logger.info(f'->> Polaris: send_msg: {msg}')
        if self._writer:
            self._writer.write(msg.encode())
            await self._writer.drain()

    async def _every_5s_send_keepalive(self):
        while True:
            msg = "h#"
            if Config.log_polaris_protocol:
                self.logger.info(f'->> Polaris: send_keepalive: {msg}')
            await self.send_msg(msg)
            await asyncio.sleep(5)

    async def every_50ms_send_message(self):
        while True:
            self.every_50ms_counter_check()
            msg = self._every_50ms_msg_to_send
            if (msg):
                await self.send_msg(msg)
            await asyncio.sleep(0.05)

    def every_50ms_counter_check(self):
        self._every_50ms_counter += 1
        # log degrees traveled per second (only do this every 5s)
        if self._every_50ms_counter >= 100:
            # reset counter and store timestamps
            self._every_50ms_counter = 0
            curr_timestamp = datetime.datetime.now()
            last_timestamp = self._every_50ms_last_timestamp
            # if we have a last recording
            if Config.log_polaris_speed and last_timestamp:
                d_alt = self._p_altitude - self._every_50ms_last_p_altitude
                d_az = self._p_azimuth - self._every_50ms_last_p_azimuth
                delta_degrees = math.sqrt(d_alt*d_alt + d_az*d_az)
                delta_seconds = (curr_timestamp - last_timestamp).total_seconds()
                if delta_seconds>0:
                    delta_dms = dec2dms(delta_degrees/delta_seconds)
                    self.logger.info(f"<<- Polaris: Avg Move Speed (Degrees:arcmin:arcsec.nn/s) - {delta_dms}/s")
            # Store values for next run
            self._every_50ms_last_timestamp = curr_timestamp
            self._every_50ms_last_p_altitude = self._p_altitude
            self._every_50ms_last_p_azimuth = self._p_azimuth

    def every_50ms_msg_to_set(self, msg):
        self._lock.acquire()
        self._every_50ms_msg_to_send = msg
        self._lock.release()
    
    def every_50ms_msg_to_clear(self):
        self._lock.acquire()
        self._every_50ms_msg_to_send = None
        self._lock.release()

    async def read_msgs(self):
        buffer = ""
        while True:
            data = None
            if self._reader:
                data = await self._reader.read(256)
                    
            # raise any subtask exceptions so polaris.client can pick them up
            if  self._task_exception:
                raise self._task_exception
                   
            if data:
                buffer += data.decode()
                parse_result = self.parse_msg(buffer)
                if parse_result:
                    buffer = parse_result[0]
                    cmd = parse_result[1]
                    if Config.log_polaris_protocol and not(cmd == "518" and Config.supress_polaris_518_msgs):
                        self.logger.info(f'<<- Polaris: recv_msg: {cmd}@{parse_result[2]}#')
                    self.polaris_parse_cmd(cmd, parse_result[2])
            else:
                # dont overload the platform trying to read data from polaris too quickly
                await asyncio.sleep(0.1)

    def parse_msg(self, msg):
        m = self._polaris_msg_re.match(msg)
        if m:
            return (msg[len(m.group(0)):],m.group(1), m.group(2))
        else:
            return False

    def polaris_parse_args(self, args_str):
        # chop the last ";" and split
        args = args_str[:-1].split(";")
        arg_dict = {}
        for arg in args:
            (name, value) = arg.split(":", 1)
            arg_dict[name] = value
        return arg_dict

    def polaris_parse_cmd(self, cmd, args):
        # return result of MODE request {} 
        if cmd == "284":
            arg_dict = self.polaris_parse_args(args)
            self._lock.acquire()
            self._current_mode = int(arg_dict['mode'])
            self._tracking = bool(arg_dict['track'] == '1') if 'track' in arg_dict else False
            self._lock.release()
            if Config.log_polaris:
                self.logger.info(f"<<- Polaris: MODE status changed: {cmd} {arg_dict}")
            if cmd in self._response_queues:
                self._response_queues[cmd].put_nowait(arg_dict)

        # return result of POSITION request {} 
        elif cmd == "518":
            arg_dict = self.polaris_parse_args(args)
            self._lock.acquire()
            self._p_azimuth = float(arg_dict['compass'])
            self._p_altitude = -float(arg_dict['alt'])
            p_ra, p_dec = self.altaz2radec(self._p_altitude, self._p_azimuth)
            self._p_rightascension = p_ra 
            self._p_declination = p_dec
            a_ra, a_dec = self.radec_polaris2ascom(p_ra, p_dec)
            self._rightascension = a_ra 
            self._declination = a_dec
            a_alt, a_az = self.radec2altaz(a_ra, a_dec)
            self._altitude = a_alt
            self._azimuth = a_az
            self._lock.release()
            if Config.log_polaris and not Config.supress_polaris_518_msgs:
                a_slew = self._slewing
                a_goto = self._gotoing
                a_track = self.tracking
                t_ra = self._targetrightascension if self._targetrightascension else a_ra       # Target Right Ascention (hours)
                t_dec = self._targetdeclination if self._targetdeclination else a_dec           # Target Declination (degrees)
                e_ra = (t_ra - a_ra)*3600*360/24                                                # Error Right Ascention (arc seconds)
                e_dec = (t_dec - a_dec)*3600                                                    # Error Declination (arc seconds)
                if not self._data1_header_timestamp:
                    self.logger.info(f",'DATA1',Time,Tracking,Slewing,Gotoing,TargetRA,TargetDEC,AscomRA,AscomDEC,AscomAz,AscomAlt,ErrorRA,ErrorDec")
                    self._data1_header_timestamp = datetime.datetime.now()
                time = (datetime.datetime.now() - self._data1_header_timestamp).total_seconds()
                self.logger.info(f",'DATA1',{time:.3f},{a_track},{a_slew},{a_goto},{t_ra:.7f},{t_dec:.7f},{a_ra:.7f},{a_dec:.7f},{a_az:.7f},{a_alt:.7f},{e_ra:.3f},{e_dec:.3f}")
        # return result of GOTO request {'ret': 'X', 'track': '1'}  X=1 (starting slew), X=2 (stopping slew)
        elif cmd == "519":
            arg_dict = self.polaris_parse_args(args)
            self._response_queues[cmd].put_nowait(arg_dict)

        # return result of TRACK change request {'ret': 'X'} where X=0 (NoTracking), X=1 (Tracking)
        elif cmd == "531":
            arg_dict = self.polaris_parse_args(args)
            self._lock.acquire()
            self._tracking = (arg_dict['ret'] == '1')
            self._lock.release()
            if Config.log_polaris:
                self.logger.info(f"<<- Polaris: TRACK status changed: {cmd} {arg_dict}")
            if cmd in self._response_queues:
                self._response_queues[cmd].put_nowait(arg_dict)

        # return result of FILE request {'type':1; 'class':0; 'path':'/app/sd/normal/SP_0052.jpg'; 'size':'916156'; 'cTime':'2023-10-24 22:33:12'; 'duration':'0'} 
        elif cmd == "771":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris:
                self.logger.info(f"<<- Polaris: FILE status changed: {cmd} {arg_dict}")

        # return result of STORAGE request {'status': '1', 'totalspace': '30420', 'freespace': '30163', 'usespace': '256'} 
        elif cmd == "775":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris:
                self.logger.info(f"<<- Polaris: STORAGE status changed: {cmd} {arg_dict}")

        # return result of BATTTERY request {'capacity': 'X', 'charge': 'Y'}  X=batttery%, Y=1 (charging), Y=0 (draining)
        elif cmd == "778":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris:
                self.logger.info(f"<<- Polaris: BATTERY status changed: {cmd} {arg_dict}")

        # return result of VERSION request {'hw':'1.3.1.4'; 'sw': '6.0.0.40'; 'exAxis':'1.0.2.11'; 'sv':'1'} 
        elif cmd == "780":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris:
                self.logger.info(f"<<- Polaris: VERSION status changed: {cmd} {arg_dict}")

        # return result of SECURITY request {'step': '1', 'password': 'YmVucm8=', 'securityQ': '2', 'securityA': 'QnJhaW4='}
        elif cmd == "790":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris:
                self.logger.info(f"<<- Polaris: SECURITY status changed: {cmd} {arg_dict}")

        # return result of WIFI request {'band': '1'}
        elif cmd == "802":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris:
                self.logger.info(f"<<- Polaris: WIFI status changed: {cmd} {arg_dict}")

        # return result of unrecognised msg
        else:
            if Config.log_polaris and not Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: response to command received: {cmd} {args}")


    def aim_altaz_log_result(self):
        self._lock.acquire()
        err_alt = self._aim_altitude - self._altitude
        err_az = self._aim_azimuth - self._azimuth
        # only fine tune the adjustment if the error was within the max correction allowed
        max = Config.aim_max_error_correction
        if abs(err_alt) < max and abs(err_az) < max:
             self._adj_altitude =  self._adj_altitude + err_alt
             self._adj_azimuth = self._adj_azimuth + err_az
        adj_alt = self._adj_altitude
        adj_az = self._adj_azimuth
        self._lock.release()
        self.logger.info(f"->> Polaris: GOTO Arc-sec Error Alt {err_alt*3600:.3f} Az {err_az*3600:.3f} | AimOffset (Alt {dec2dms(adj_alt)} Az {dec2dms(adj_az)})")

    def aim_altaz_log_and_correct(self, alt: float, az:float):
        # log the original aiming co-ordinates and grab the last error ajustments
        self._lock.acquire()
        self._aim_altitude = alt
        self._aim_azimuth = az
        adj_alt = self._adj_altitude
        adj_az = self._adj_azimuth
        self._lock.release()

        # ajust the aiming altaz and clap az being sent to the Polaris -180° < polaris_az < 180°
        calt = alt + adj_alt if Config.aiming_adjustment_enabled else alt
        caz = az + adj_az if Config.aiming_adjustment_enabled else az
        caz = 360 - caz if caz>180 else -caz
        return (calt, caz)

    async def send_cmd_change_tracking_state(self, tracking: bool):
        cmd = '531'
        state = 1 if tracking else 0
        if Config.log_polaris:
            self.logger.info(f"->> Polaris: TRACK request change to {state}")
        empty_queue(self._response_queues[cmd])
        await self.send_msg(f"1&{cmd}&3&state:{state};speed:0;#")
        await self._response_queues[cmd].get() 

    # Assumes polaris altaz
    async def send_cmd_goto_altaz(self, alt, az, istracking = True):
        self._lock.acquire()
        currently_slewing = self._slewing
        currently_gotoing = self._gotoing
        currently_tracking = self._tracking
        self._lock.release()

        # if we are currently slewing or gotoing, dont try again
        if currently_slewing or currently_gotoing:
            return

        # Mark that we are gotoing and slewing
        self._lock.acquire()
        self._slewing = True
        self._gotoing = True
        self._lock.release()

        # log the command
        if Config.log_polaris:
            self.logger.info(f"->> Polaris: GOTO Polaris Alt {dec2dms(alt)} Az {dec2dms(az)} ")

        # log the aiming alt/az and correct it based on previous aiming results
        calt, caz = self.aim_altaz_log_and_correct(alt, az)
        # calt = alt
        # caz = 360 - az if az>180 else -az

        # if we are currently sidereal tracking then turn off tracking
        if currently_tracking:
            await self.send_cmd_change_tracking_state(False)

        # compose and send the GOTO message
        finaltrack = 1 if istracking else 0
        cmd = '519'
        msg = f"1&{cmd}&3&state:1;yaw:{caz:.5f};pitch:{calt:.5f};lat:{self._sitelatitude:.5f};track:{finaltrack};speed:0;lng:{self._sitelongitude:.5f};#"
        empty_queue(self._response_queues[cmd])
        await self.send_msg(msg)

        # Wait for 1st response of slew started
        ret_dict = await self._response_queues[cmd].get()
        if Config.log_polaris:
            self.logger.info(f"<<- Polaris: GOTO starting slew: {cmd} {ret_dict}")
            
        # wait for 2nd response of slew stopped
        ret_dict = await self._response_queues[cmd].get()
        if Config.log_polaris:
            self.logger.info(f"<<- Polaris: GOTO stopping slew: {cmd} {ret_dict}")

        # wait for sidereal tracking to settle
        await asyncio.sleep(Config.tracking_settle_time)

        # mark the slew as complete      
        self._lock.acquire()
        self._slewing = False
        self._gotoing = False
        self._lock.release()
        if Config.log_polaris:
            self.logger.info(f"<<- Polaris: GOTO slew complete")

        # log the result of the goto
        self.aim_altaz_log_result()

        return ret_dict

    async def send_cmd_reset_axis(self, axis:int):
        if axis==1 or axis==2 or axis==3:
            await self.send_msg(f"1&523&3&axis:{axis};#")

    async def send_cmd_park(self):
        await self.send_cmd_reset_axis(1)
        await self.send_cmd_reset_axis(2)
        await self.send_cmd_reset_axis(3)

    async def get_current_mode(self):
        if Config.log_polaris:
            self.logger.info(f"->> Polaris: MODE status info request")
        cmd = '284'
        msg = f"1&{cmd}&2&-1#"
        empty_queue(self._response_queues[cmd])
        await self.send_msg(msg)
        ret_dict = await self._response_queues[cmd].get()
        return ret_dict


    async def polaris_init(self):
        self.logger.info("Polaris communication init...")
        ret_dict = await self.get_current_mode()
        if  'mode' in ret_dict and int(ret_dict['mode']) == 8:
            if 'track' in ret_dict and int(ret_dict['track']) == 3:
                # Polaris is in astro mode but alignment not complete
                raise AstroAlignmentError()
            self.logger.info("Polaris communication init... done")
            self.logger.info(f'Site lat = {self._sitelatitude} lon = {self._sitelongitude}. Change in config.toml or use Nina to sync.')
            self._lock.acquire()
            self._connected = True
            self._task_errorstr = ''
            self._lock.release()
        else:
            # Polaris is not in astro mode
            raise AstroModeError()

    #
    # Telescope device states
    #
    @property
    def connected(self) -> bool:
        self._lock.acquire()
        res = self._connected
        self._lock.release()
        return res

    def connectionquery(self, client: str):
        self._lock.acquire()
        # if no record of client, assume it was connected so that it can continue working
        if not client in self._connections:
            self._connections[client] = True
        res = self._connections[client]
        self._lock.release()
        return res
                          
    def connectionrequest(self, client: str, connect: bool):
        self._lock.acquire()
        self._connections[client] = connect
        numclients = sum(v for v in self._connections.values() if v)
        self._lock.release()
        if Config.log_polaris:
            self.logger.info(f'[connection request] Client {client} Connected: {connect} Total Connected Clients: {numclients}')

        # check is any exceptions with polaris.client() and polaris_init() last run
        if  self._task_errorstr:
            raise Exception(self._task_errorstr)
        
    @property
    def tracking(self) -> bool:
        self._lock.acquire()
        res = self._tracking
        self._lock.release()
        return res
    @tracking.setter
    def tracking (self, tracking: int):
        self._lock.acquire()
        self._tracking = tracking
        self._lock.release()

    @property
    def sideofpier(self) -> int:
        self._lock.acquire()
        res =  self._sideofpier
        self._lock.release()
        return res
    @sideofpier.setter
    def sideofpier (self, sideofpier: int):
        self._lock.acquire()
        self._sideofpier = sideofpier
        self._lock.release()

    @property
    def athome(self) -> bool:
        self._lock.acquire()
        res =  self._athome
        self._lock.release()
        return res

    @property
    def atpark(self) -> bool:
        self._lock.acquire()
        res =  self._atpark
        self._lock.release()
        return res

    @property
    def slewing(self) -> bool:
        self._lock.acquire()
        res =  self._slewing
        self._lock.release()
        return res

    @property
    def gotoing(self) -> bool:
        self._lock.acquire()
        res =  self._gotoing
        self._lock.release()
        return res

    @property
    def ispulseguiding(self) -> bool:
        self._lock.acquire()
        res =  self._ispulseguiding
        self._lock.release()
        return res
    #
    # Telescope device variables
    #
    @property
    def altitude(self) -> float:
        self._lock.acquire()
        res =  self._altitude
        self._lock.release()
        return res

    @property
    def azimuth(self) -> float:
        self._lock.acquire()
        res =  self._azimuth
        self._lock.release()
        return res

    @property
    def declination(self) -> float:
        self._lock.acquire()
        res =  self._declination
        self._lock.release()
        return res

    @property
    def rightascension(self) -> float:
        self._lock.acquire()
        res =  self._rightascension
        self._lock.release()
        return res

    @property
    def siderealtime(self) -> float:
        self._observer.date = datetime.datetime.now(tz=datetime.timezone.utc)
        res =  self._observer.sidereal_time()/2/math.pi*24
        return res

    @property
    def utcdate(self) -> datetime.datetime:
        res = datetime.datetime.now(datetime.timezone.utc).isoformat().split('+')[0]
        return res

    #
    # Telescope device rates
    #
    @property
    def trackingrate(self) -> int:
        self._lock.acquire()
        res =  self._trackingrate
        self._lock.release()
        return res
    @trackingrate.setter
    def trackingrate (self, trackingrate: int):
        self._lock.acquire()
        self._trackingrate = trackingrate
        self._lock.release()

    @property
    def trackingrates(self):
        self._lock.acquire()
        res =  self._trackingrates
        self._lock.release()
        return res

    @property
    def declinationrate(self) -> float:
        self._lock.acquire()
        res =  self._declinationrate
        self._lock.release()
        return res
    @declinationrate.setter
    def declinationrate (self, declinationrate: float):
        self._lock.acquire()
        self._declinationrate = declinationrate
        self._lock.release()

    @property
    def rightascensionrate(self) -> float:
        self._lock.acquire()
        res =  self._rightascensionrate
        self._lock.release()
        return res
    @rightascensionrate.setter
    def rightascensionrate (self, rightascensionrate: float):
        self._lock.acquire()
        self._rightascensionrate = rightascensionrate
        self._lock.release()

    @property
    def guideratedeclination(self) -> float:
        self._lock.acquire()
        res =  self._guideratedeclination
        self._lock.release()
        return res
    @guideratedeclination.setter
    def guideratedeclination (self, guideratedeclination: float):
        self._lock.acquire()
        self._guideratedeclination = guideratedeclination
        self._lock.release()

    @property
    def guideraterightascension(self) -> float:
        self._lock.acquire()
        res =  self._guideraterightascension
        self._lock.release()
        return res
    @guideraterightascension.setter
    def guideraterightascension (self, guideraterightascension: float):
        self._lock.acquire()
        self._guideraterightascension = guideraterightascension
        self._lock.release()
    #
    # Telescope device settings
    #
    @property
    def alignmentmode(self) -> int:
        self._lock.acquire()
        res =  self._alignmentmode
        self._lock.release()
        return res

    @property
    def aperturearea(self) -> float:
        self._lock.acquire()
        res =  self._aperturearea
        self._lock.release()
        return res

    @property
    def aperturediameter(self) -> float:
        self._lock.acquire()
        res =  self._aperturediameter
        self._lock.release()
        return res

    @property
    def equatorialsystem(self) -> float:
        self._lock.acquire()
        res =  self._equatorialsystem
        self._lock.release()
        return res

    @property
    def focallength(self) -> float:
        self._lock.acquire()
        res = self._focallength
        self._lock.release()
        return res

    @property
    def siteelevation(self) -> float:
        self._lock.acquire()
        res = self._siteelevation
        self._lock.release()
        return res
    @siteelevation.setter
    def siteelevation (self, siteelevation: float):
        self._lock.acquire()
        self._siteelevation = siteelevation
        self._lock.release()

    @property
    def sitelatitude(self) -> float:
        self._lock.acquire()
        res = self._sitelatitude
        self._lock.release()
        return res
    @sitelatitude.setter
    def sitelatitude (self, sitelatitude: float):
        self._lock.acquire()
        self._sitelatitude = sitelatitude
        self._observer.lat = dec2dms(sitelatitude) 
        self._lock.release()

    @property
    def sitelongitude(self) -> float:
        self._lock.acquire()
        res =  self._sitelongitude
        self._lock.release()
        return res
    @sitelongitude.setter
    def sitelongitude (self, sitelongitude: float):
        self._lock.acquire()
        self._sitelongitude = sitelongitude
        self._observer.long = dec2dms(sitelongitude) 
        self._lock.release()
    
    @property
    def slewsettletime(self) -> int:
        self._lock.acquire()
        res =  self._slewsettletime
        self._lock.release()
        return res
    @slewsettletime.setter
    def slewsettletime (self, slewsettletime: int):
        self._lock.acquire()
        self._slewsettletime = slewsettletime
        self._lock.release()

    @property
    def supportedactions(self) -> float:
        self._lock.acquire()
        res =  self._supportedactions
        self._lock.release()
        return res

    @property
    def targetdeclination(self) -> float:
        self._lock.acquire()
        res =  self._targetdeclination
        self._lock.release()
        return res
    @targetdeclination.setter
    def targetdeclination (self, targetdeclination: float):
        self._lock.acquire()
        self._targetdeclination = targetdeclination
        self._lock.release()

    @property
    def targetrightascension(self) -> float:
        self._lock.acquire()
        res =  self._targetrightascension
        self._lock.release()
        return res
    @targetrightascension.setter
    def targetrightascension (self, targetrightascension: float):
        self._lock.acquire()
        self._targetrightascension = targetrightascension
        self._lock.release()
    #
    # Telescope capability constants
    #
    @property
    def canfindhome(self) -> bool:
        self._lock.acquire()
        res =  self._canfindhome
        self._lock.release()
        return res

    @property
    def canpark(self) -> bool:
        self._lock.acquire()
        res =  self._canpark
        self._lock.release()
        return res

    @property
    def canpulseguide(self) -> bool:
        self._lock.acquire()
        res =  self._canpulseguide
        self._lock.release()
        return res

    @property
    def cansetdeclinationrate(self) -> bool:
        self._lock.acquire()
        res =  self._cansetdeclinationrate
        self._lock.release()
        return res

    @property
    def cansetguiderates(self) -> bool:
        self._lock.acquire()
        res =  self._cansetguiderates
        self._lock.release()
        return res

    @property
    def cansetpark(self) -> bool:
        self._lock.acquire()
        res =  self._cansetpark
        self._lock.release()
        return res

    @property
    def cansetpierside(self) -> bool:
        self._lock.acquire()
        res =  self._cansetpierside
        self._lock.release()
        return res

    @property
    def cansetrightascensionrate(self) -> bool:
        self._lock.acquire()
        res =  self._cansetrightascensionrate
        self._lock.release()
        return res

    @property
    def cansettracking(self) -> bool:
        self._lock.acquire()
        res =  self._cansettracking
        self._lock.release()
        return res

    @property
    def canslew(self) -> bool:
        self._lock.acquire()
        res =  self._canslew
        self._lock.release()
        return res

    @property
    def canslewasync(self) -> bool:
        self._lock.acquire()
        res =  self._canslewasync
        self._lock.release()
        return res

    @property
    def canslewaltaz(self) -> bool:
        self._lock.acquire()
        res =  self._canslewaltaz
        self._lock.release()
        return res

    @property
    def canslewaltazasync(self) -> bool:
        self._lock.acquire()
        res =  self._canslewaltazasync
        self._lock.release()
        return res

    @property
    def cansync(self) -> bool:
        self._lock.acquire()
        res =  self._cansync
        self._lock.release()
        return res

    @property
    def cansyncaltaz(self) -> bool:
        self._lock.acquire()
        res =  self._cansyncaltaz
        self._lock.release()
        return res

    @property
    def canunpark(self) -> bool:
        self._lock.acquire()
        res =  self._canunpark
        self._lock.release()
        return res

    @property
    def doesrefraction(self) -> bool:
        self._lock.acquire()
        res =  self._doesrefraction
        self._lock.release()
        return res
    @doesrefraction.setter
    def doesrefraction (self, doesrefraction: float):
        self._lock.acquire()
        self._doesrefraction = doesrefraction
        self._lock.release()
    #
    # Telescope method constants
    #
    @property
    def axisrates(self) -> bool:
        self._lock.acquire()
        res =  self._axisrates
        self._lock.release()
        return res

    @property
    def canmoveaxis(self) -> bool:
        self._lock.acquire()
        res =  self._canmoveaxis
        self._lock.release()
        return res

    
    


    ####################################################################
    # Methods
    ####################################################################
    async def SlewToCoordinates(self, rightascension, declination, isasync = True) -> None:
        a_ra = rightascension
        a_dec = declination
        self._lock.acquire()
        self._targetrightascension = a_ra
        self._targetdeclination = a_dec
        self._lock.release()
        p_ra, p_dec = self.radec_ascom2polaris(a_ra, a_dec)
        o_ra = self._adj_rightascension
        o_dec = self._adj_declination
        # want to work out its Alt/Az of where it will be in the future, as it takes at least this time to settle.
        inthefuture = Config.aiming_adjustment_time if Config.aiming_adjustment_enabled else 0
        p_alt, p_az = self.radec2altaz(p_ra, p_dec, inthefuture)
        self.logger.info(f"->> Polaris: GOTO ASCOM RA {dec2dms(a_ra)} Dec {dec2dms(a_dec)}")
        self.logger.info(f"->> Polaris: GOTO Polaris RA {dec2dms(p_ra)} Dec: {dec2dms(p_dec)} | SyncOffset (RA {dec2dms(o_ra)} Dec {dec2dms(o_dec)})")
        if isasync:
            asyncio.create_task(self.send_cmd_goto_altaz(p_alt, p_az, istracking=True))
        else:
            await self.send_cmd_goto_altaz(p_alt, p_az, istracking=True)

    async def SlewToAltAz(self, altitude, azimuth, isasync = True) -> None:
        a_alt = altitude
        a_az = azimuth
        a_ra, a_dec = self.altaz2radec(a_alt, a_az)
        self.logger.info(f"->> Polaris: GOTO ASCOM Alt: {dec2dms(a_alt)} Az: {dec2dms(a_az)}")
        await self.SlewToCoordinates(a_ra, a_dec, isasync)

    def convert_ascom2polaris_rate(self, axis: int, ascomrate: float):
        # Map between ASCOM floatinig to Polaris rates for Slow and Fast Move
        # __ASCOM RATE__:_POLARIS RATE__|__Aprox Speed__|_CMD__________________________________
        # 0.000         : 0             |               | Stop all
        # 0.001 to 1.000: 1             | 21.5 arcsec/s  | Slow move commands '532', '533', '534'
        # 1.001 to 2.000: 2             |  1.1 arcmin/s  |   "
        # 2.001 to 3.000: 3             |  2.8 arcmin/s  |   "
        # 3.001 to 4.000: 4             |  5.3 arcmin/s  |   "
        # 4.001 to 5.000: 5             | 12.5 arcmin/s  |   "
        # 5.001 to 6.000: 1 to 500      | 32.5 arcmin/s  | Fast move commands '513', '514', '521'
        # 6.001 to 7.000: 501 to 1000   |  1.5 degree/s  |   "
        # 7.001 to 8.000: 1001 to 1500  |  3.0 degree/s  |   "
        # 8.001 to 9.000: 1501 to 2000  |  5.2 degree/s  |   "
        
        # Number of units in each group for rates 6, 7, 8, 9 - MUST TOTAL 2000
        group6 = 500
        group7 = 500
        group8 = 500
        group9 = 500

        sign = -1 if ascomrate < 0 else 1
        key = 0 if ascomrate > 0 else 1
        x = abs(ascomrate)

        if x==0:
            rate = 0
        elif x <= 1.0:
            rate = 1
        elif x <= 2.0:
            rate = 2
        elif x <= 3.0:
            rate = 3
        elif x <= 4.0:
            rate = 4
        elif x <= 5.0:
            rate = 5
        elif x <= 6.0:
            rate = int(1 + (x - 5.0) * (group6 - 1))                              # (1 + (x - 4.0) * 499)
        elif x <= 7.0:
            rate = int(group6 + 1 + (x - 6.0) * (group7 - 1))                     # (501 + (x - 5.0) * 499)
        elif x <= 8.0:
            rate = int(group6 + group7 + 1 + (x - 7.0) * (group8 - 1))            # (1001 + (x - 6.0) * 499)
        elif x <= 9.0:
            rate = int(group6 + group7 + group8 + 1 + (x - 8.0) * (group9 - 1))   # (1501 + (x - 7.0) * 499)
        else:
            rate = None
        
        # calc the cmd based on axis and whether slow or fast (use +/-2000)
        if x <= 5.0:
            cmd = '532' if axis==0 else '533' if axis==1 else '534'
            cmdtype = 1   # slow commands
        elif x<=9.0:
            key = None
            rate = sign * rate
            cmd = '513' if axis==0 else '514' if axis==1 else '521'
            cmdtype = 2   # fast commands
        
        # special extended commands should be moved to ASCOM extensions
        elif x<=10.0:
            cmd = None
            cmdtype = 3   # 3 point alignment - move 15 degrees from current axis 0=RA, 1=Dec, 
        elif x<=11.0:
            cmd = None
            cmdtype = 4   # 3 point alignment - start BP alignment from current pos
        elif x<=12.0:
            cmd = None
            cmdtype = 5   # 3 point alignment - move (X-11)*10 deg from current eg 11.51 = 5.1'
            rate = (ascomrate - 11.0) * 10.0
        elif x<=13.0:
            cmd = None
            cmdtype = 6   # 3 point alignment - Finish BP alignment
        else:
            cmd = None
            cmdtype = None
            rate = 0
            key=0
            
        return cmd, cmdtype, key, rate           


    async def move_axis(self, axis:int, ascomrate:float):
        cmd, cmdtype, key, rate = self.convert_ascom2polaris_rate(axis, ascomrate)

        # f cmdtype=1 then slow Alt/Az move and stop slow or fast
        if cmdtype==1:
            if Config.log_polaris:
                self.logger.info(f"->> Polaris: MOVE Slow Az/Alt/Rot Axis {axis} Rate {rate}")
            self._lock.acquire()
            self._axis_slow_slewing[axis] = rate
            self._slewing = any(self._axis_slow_slewing)
            self._lock.release()
            if self._every_50ms_msg_to_send and rate == 0:
                self.every_50ms_msg_to_clear()                  # stop fast move msgs
                if Config.log_polaris_protocol:
                    self.logger.info(f'->> Polaris: stop_fastmove_repeating')
            state = 0 if rate == 0 else 1
            await self.send_msg(f"1&{cmd}&3&key:{key};state:{state};level:{rate};#")

        # if cmdtype=2 then fast Alt/Az move
        elif cmdtype==2:
            self._lock.acquire()
            self._slewing = True
            self._lock.release()
            msg=f"1&{cmd}&3&speed:{rate};#"
            if Config.log_polaris:
                self.logger.info(f"->> Polaris: MOVE Fast Az/Alt/Rot Axis {axis} Rate {rate}")
            if Config.log_polaris_protocol:
                self.logger.info(f'->> Polaris: send_fastmove_repeating: {msg}')
            self.every_50ms_msg_to_set(msg)                     # start fast move msgs

        # if cmdtype=3 then assume RA/Dec move 15 degrees
        elif cmdtype==3:
            if Config.log_polaris:
                self.logger.info(f"->> Polaris: 3 Point Alignment: A. MOVE RA/Dec Axis {axis} 15 degrees")
            self._lock.acquire()
            ra = self._rightascension + ((15.0*24/360) if axis==0 else 0)
            dec = self._declination + (15.0 if axis==1 else 0)
            self._lock.release()
            await self.SlewToCoordinates(ra, dec, isasync=True)

        # if cmdtype=4 then start alignment process
        elif cmdtype==4:
            if Config.log_polaris:
                self.logger.info(f"->> Polaris: 3 Point Alignment: B. Start Start Alignment")
            self._lock.acquire()
            ra = self._rightascension 
            dec = self._declination
            self._lock.release()

        # if cmdtype=5 then end alignment processmove (X-10)*10 deg from current eg 10.51 = 5.1'
        elif cmdtype==5:
            if Config.log_polaris:
                self.logger.info(f"->> Polaris: 3 Point Alignment: B. Start Start Alignment")
            self._lock.acquire()
            ra = self._rightascension 
            dec = self._declination
            self._lock.release()

    async def park(self):
        self._lock.acquire()
        self._atpark = True
        self._adj_declination = 0
        self._adj_rightascension = 0
        self._adj_altitude = 0
        self._adj_azimuth = 0
        self._lock.release()
        await self.send_cmd_park()

    async def unpark(self):
        self._lock.acquire()
        self._atpark = False
        self._lock.release()

