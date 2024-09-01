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
# * retry connecting to polaris if not currently
# * provide proper error messages when ASMCOM connect put (no wifi connect, no ip network, no Astro mode, no Alignment)
# * cater for comms error (lose comms, lose wifi, change mode)
# * error check before using self._writer or self._reader
# * Improve exception handling
# * Add retries for when comms fails to Polaris
# * Use Wireshark to determine 
# *   cmds for move N S W E and Rotate
# *   cmd for Park NSWE and Park Rotate
# * Determine tracking on settle time 16s
# * Determine nina ASCOM commands for platesolve slew, center and rotate
# * Determine nina ASCOM commands for platesolve co-rdinates sync
# DONE:
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

def dec2dms(dd):
   is_positive = dd >= 0
   dd = abs(dd)
   minutes,seconds = divmod(dd*3600,60)
   degrees,minutes = divmod(minutes,60)
   degrees = degrees if is_positive else -degrees
   return f"{int(degrees)}:{int(minutes)}:{seconds:.2f}"

def dms2dec(dms):
    (degree, minute, second, frac_seconds) = re.split(r'[^0-9-]', dms, maxsplit=4)
    return int(degree) + float(minute) / 60 + float(second) / 3600 + float(frac_seconds) / 360000

def rad2hr(rad):
    return rad*24/2/math.pi

def hr2rad(hr):
    return hr*2*math.pi/24

def rad2deg(rad):
    return rad*360/2/math.pi

def deg2rad(deg):
    return deg*2*math.pi/360

def empty_queue(q: asyncio.Queue):
  while not q.empty():
    try:
        q.get_nowait()
    except asyncio.QueueEmpty:
        break

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
        self._connected: bool = True                # Polaris connection status. True if any client is connected. False when all clients have left.
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
        self._siderealtime: float = 0.0             # The local apparent sidereal time from the telescope's internal clock (hours, sidereal)
        self._aim_altitude: float = 0.0             # The Altitude of the last goto command
        self._aim_azimuth: float = 0.0              # The Azimuth of the last goto command
        self._adj_altitude: float = Config.aiming_adjustment_alt    # The Altitude adjustment to correct the aim based on past goto results
        self._adj_azimuth: float = Config.aiming_adjustment_az      # The Azimuth adjustment to correct the aim based on past goto results
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
        self._cansync: bool = False                 # True if this telescope is capable of programmed synching to equatorial coordinates.
        self._cansyncaltaz: bool = False             # True if this telescope is capable of programmed synching to local horizontal coordinates
        self._canunpark: bool = True                # True if this telescope is capable of programmed unparking (Unpark() method).
        self._doesrefraction: bool = False          # True if the telescope or driver applies atmospheric refraction to coordinates.
        #
        # Telescope method constants
        #
        self._axisrates = [{ "Maximum":20, "Minimum":1 }] # Describes a range of rates supported by the MoveAxis(TelescopeAxes, Double) method (degrees/per second)   
        self._axisslewing = [ 0, 0, 0 ]                  # Records the move rate of the primary, seconday and tertiary axis
        self._canmoveaxis = [ True, True, True ]         # True if this telescope can move the requested axis



    ########################################
    # POLARIS COMMUNICATIONS METHODS 
    ########################################

# Exceptions
# ConnectionAbortedError [WinError 1236] The network connection was aborted by the local system
# OSError [error 22][WinError 121] The semaphore timeout period has expired

    # open connection and serve as polaris client
    async def client(self, logger: Logger):
        # Assumes that wifi network is already connected and routed to Polaris device
        # netsh wlan connect name="polaris_3b3906" interface="Wi-Fi USB"
        while True:
            try:
                self._task_exception = None
                client_reader, client_writer = await asyncio.open_connection(Config.polaris_ip_address, Config.polaris_port)
                self._reader = client_reader
                self._writer = client_writer
                logger.info(f'==STARTUP== Polaris Client on {Config.polaris_ip_address}:{Config.polaris_port}. ')
                task = asyncio.create_task(self.polaris_init())
                task.add_done_callback(self.task_done)
                await self.read_msgs()

            except ConnectionAbortedError as e:
                self._task_errorstr = f'==STARTUP== The Polaris network connection was aborted.'
                logger.error(self._task_errorstr)
                await asyncio.sleep(5)
                continue

            except OSError as e:
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

    async def send_msg(self, msg):
        if Config.log_polaris_protocol:
            self.logger.info(f'->> Polaris: send_msg: {msg}')
        self._writer.write(msg.encode())
        await self._writer.drain()

    async def read_msgs(self):
        buffer = ""
        while True:
            data = await self._reader.read(256)

            # raise any subtask exceptions so polaris.client can pick them up
            if  self._task_exception:
                raise self._task_exception       

            if not data:
                break
            buffer += data.decode()
            parse_result = self.parse_msg(buffer)
            if parse_result:
                buffer = parse_result[0]
                cmd = parse_result[1]
                if Config.log_polaris_protocol and not(cmd == "518" and Config.supress_polaris_518_msgs):
                    self.logger.info(f'<<- Polaris: recv_msg: {cmd}@{parse_result[2]}#')
                self.polaris_parse_cmd(cmd, parse_result[2])

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
            self._azimuth = float(arg_dict['compass'])
            self._altitude = -float(arg_dict['alt'])
            self._observer.date = datetime.datetime.now(tz=datetime.timezone.utc)
            ra, dec = self._observer.radec_of(deg2rad(self._azimuth), deg2rad(self._altitude))
            self._rightascension = rad2hr(ra)  
            self._declination = rad2deg(dec)
            self._lock.release()
            if Config.log_polaris and not Config.supress_polaris_518_msgs:
                self.logger.info(f"<<- Polaris: POSITION status changed: {cmd} {arg_dict}")

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
                self.logger.info(f"<<- Polaris: response to command received {cmd} {args}")


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
        self.logger.info(f"->> Polaris: GOTO error az={err_alt} alt={err_az}, adjustment az={adj_alt} alt={adj_az}")

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
            self.logger.info(f"->> Polaris: GOTO Az.:{az:.5f} Alt.:{alt:.5f}")

        # log the aiming alt/az and correct it based on previous aiming results
        calt, caz = self.aim_altaz_log_and_correct(alt, az)

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
            self.logger.info(f'[connection request] Client {client} Connected: {connect}, Total Connected Clients: {numclients}')

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

    def park(self):
        self._lock.acquire()
        self._atpark = True
        self._lock.release()

    def unpark(self):
        self._lock.acquire()
        self._atpark = False
        self._lock.release()

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
        self._lock.acquire()
        self._targetrightascension = rightascension
        self._targetdeclination = declination
        self._rightascension = rightascension
        self._declination = declination
        target = ephem.FixedBody()
        target._ra = hr2rad(rightascension)
        target._dec = deg2rad(declination)
        target._epoch = ephem.J2000
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        # want to work out its Alt/Az of where it will be in the future, as it takes at least this time to settle.
        inthefuture = Config.aiming_adjustment_time if Config.aiming_adjustment_enabled else 0
        self._observer.date = now + datetime.timedelta(seconds=inthefuture)
        target.compute(self._observer)
        self._lock.release()
        self.logger.info(f"->> Polaris: GOTO UT RA: {target.ra} Dec: {target.dec} -> Az.: {target.az} Alt.: {target.alt}")
        alt = rad2deg(target.alt)
        az = rad2deg(target.az)
        await self.SlewToAltAz(alt, az, isasync)

    async def SlewToAltAz(self, altitude, azimuth, isasync = True) -> None:
        self._lock.acquire()
        self._altitude = altitude
        self._azimuth = azimuth
        self._lock.release()
        if isasync:
            asyncio.create_task(self.send_cmd_goto_altaz(altitude, azimuth, istracking=True))
        else:
            await self.send_cmd_goto_altaz(altitude, azimuth, istracking=True)

    async def move_axis(self, axis:int, rate:float):
        # if rate is greater than 5 than assume RA/Dec move in degrees
        if abs(rate) > 5:
            if Config.log_polaris:
                self.logger.info(f"->> Polaris: MOVE RA/Dec Axis {axis}, Rate {rate}")
            self._lock.acquire()
            ra = self._rightascension + ((rate*24/360) if axis==0 else 0)
            dec = self._declination + (rate if axis==1 else 0)
            self._lock.release()
            await self.SlewToCoordinates(ra, dec, isasync=True)

        # otherwise assume its a fine tune Alt/Az move
        else:
            if Config.log_polaris:
                self.logger.info(f"->> Polaris: MOVE Az/Alt/Rot Axis {axis}, Rate {rate}")
            self._lock.acquire()
            floor_rate = math.floor(rate)
            self._axisslewing[axis] = floor_rate
            self._slewing = any(self._axisslewing)
            self._lock.release()
            await self.send_move_cmd(axis, floor_rate)

    async def send_move_cmd(self, axis: int, rate: int):
        cmd = '532' if axis==0 else '533' if axis==1 else '534'
        key = 0 if rate > 0 else 1
        state = 0 if rate == 0 else 1
        level = abs(rate) 
        await self.send_msg(f"1&{cmd}&3&key:{key};state:{state};level:{level};#")

# ./arpspoof.exe 192.168.0.2

# LHS Fast Top Left  = f"1&514&3&speed:2000;#" f"1&513&3&speed:-2000;#"
# LHS Fast Top Right = f"1&514&3&speed:2000;#" f"1&513&3&speed:2000;#"
# LHS Fast Bottom Left = f"1&514&3&speed:-2000;#" f"1&513&3&speed:-2000;#"
# LHS Fast Bottom Right = f"1&514&3&speed:-2000;#" f"1&513&3&speed:2000;#"
# LHS Slow Top Left  = f"1&514&3&speed:200;#" f"1&513&3&speed:-200;#"
# LHS Slow Top Right = f"1&514&3&speed:200;#" f"1&513&3&speed:200;#"
# LHS Slow Bottom Left = f"1&514&3&speed:-200;#" f"1&513&3&speed:-200;#"
# LHS Slow Bottom Right = f"1&514&3&speed:-200;#" f"1&513&3&speed:200;#"
# LHS Double Tap = f"1&523&3&axis:1;#" f"1&523&3&axis:2;#"

# RHS Fast Right = f"1&521&3&speed:2000;#"
# RHS Fast Left = f"1&521&3&speed:-2000;#"
# RHS Double Tap = f"1&523&3&axis:3;#"

# Realign with Rigil Kentaurus f"519@ret:1;track:0;#518@w:-0.0545174;x:-0.9174206;y:0.1566324;z:-0.3617094;w:-0.3617094;x:-0.9174206;y:0.1566323;z:0.0545174;compass:288.2599487;alt:-47.0869865;#518@w:-0.0545175;x:-0.9174200;y:0.1566319;z:-0.3617111;w:-0.3617111;x:-0.9174200;y:0.1566319;z:0.0545175;compass:288.2599182;alt:-47.0867844;#518@w:-0.0545171;x:-0.9174206;y:0.1566316;z:-0.3617100;w:-0.3617100;x:-0.9174206;y:0.1566315;z:0.0545171;compass:288.2598572;alt:-47.0869370;#518@w:-0.0545176;x:-0.9174200;y:0.1566319;z:-0.3617115;w:-0.3617115;x:-0.9174200;y:0.1566319;z:0.0545176;compass:288.2599182;alt:-47.0867500;#518@w:-0.0628244;x:-0.9168891;y:0.1599009;z:-0.3602772;w:-0.3602772;x:-0.9168891;y:0.1599008;z:0.0628244;compass:289.7843018;alt:-47.0969810;#518@w:-0.0628249;x:-0.9168892;y:0.1599023;z:-0.3602764;w:-0.3602764;x:-0.9168891;y:0.1599023;z:0.0628250;compass:289.7844849;alt:-47.0970840;#518@w:-0.0627151;x:-0.9170070;y:0.1597574;z:-0.3600599;w:-0.3600599;x:-0.9170069;y:0.1597574;z:0.0627151;compass:289.7633057;alt:-47.1256409;#518@w:0.0611517;x:0.9191911;y:-0.1567659;z:0.3560515;w:0.3560515;x:0.9191911;y:-0.1567659;z:-0.0611518;compass:289.4240112;alt:-47.6442299;#518@w:0.0593493;x:0.9208599;y:-0.1539250;z:0.3532738;w:0.3532738;x:0.9208598;y:-0.1539250;z:-0.0593493;compass:289.0260010;alt:-48.0176392;#518@w:0.0573002;x:0.9226959;y:-0.1505630;z:0.3502569;w:0.3502569;x:0.9226958;y:-0.1505629;z:-0.0573002;compass:288.5586548;alt:-48.4237633;#
# Confirm = f"1&530&3&step:2;yaw:151.342;pitch:54.93;lat:-33.655266;num:1;lng:151.12234;#