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
# * Correct for Drift
# DONE:
# * Implement ASCOM sync
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
import time
import re
import asyncio
import ephem
import json
import numpy as np
from collections import deque
from pyquaternion import Quaternion
from threading import Lock
from logging import Logger
from config import Config
from exceptions import AstroModeError, AstroAlignmentError, WatchdogError
from shr import deg2rad, rad2hr, rad2deg, hr2rad, deg2dms, hr2hms, clamparcsec, empty_queue
from control import KalmanFilter, quaternion_to_angles, calculate_angular_velocity, is_angle_same, format_move_axis_data, generate_mpc_strategy, MotorSpeedController, PID_Controller
from scipy.interpolate import PchipInterpolator

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
        self._startup_timestamp = datetime.datetime.now()  # Timestamp for when the driver started.
        self._performance_data_start_timestamp = None      # Timestamp for Performance Data logging.
        self._last_518_timestamp = None                    # Timestamp for last 518 Position Update message from Polaris.
        self._task_exception = None                 # record of any exception from sub tasks
        self._task_errorstr = ''                    # record of any connection issues with polaris (reset at next attempt to reconnect)
        self._task_errorstr_last_attempt = ''       # record of any connection issues with polaris
        self._N_point_alignment_results = {}        # record of all sync results for N point alignment
        self._test_underway = False                 # flag to mark that a test is underway and executing
        #
        # Polaris site/device location variables
        #
        self._sitelatitude: float = float(Config.site_latitude)     # The geodetic(map) latitude (degrees, positive North, WGS84) of the site at which the telescope is located.
        self._sitelongitude: float = float(Config.site_longitude)   # The longitude (degrees, positive East, WGS84) of the site at which the telescope is located.
        self._siteelevation: float = float(Config.site_elevation)   # The elevation above mean sea level (meters) of the site at which the telescope is located
        self._observer = ephem.Observer()                           # Observer object for the telescopes site
        self._observer.pressure = Config.site_pressure              # site pressure used for refraction calculations close to horizon
        self._observer.epoch = ephem.J2000                          # a moment in time used as a reference point for RA/Dec
        self._observer.lat = deg2rad(self._sitelatitude)            # dms version on lat
        self._observer.long = deg2rad(self._sitelongitude)          # dms version of long
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
        self._kf: KalmanFilter = KalmanFilter(logger, np.zeros(6))
        self._q1 = None                             # The latest quaternion mapping Camera Co-ordinates Framework to Topocentric Co-ordinates Framework
        self._theta_meas = None                     # The latest set of motor axis angles [theta1, theta2, theta3] measured from q1
        self._omega_meas = None                     # The latest set of motor axis angular velocity [omega1, omega2, omega3] measured from q1
        self._mpc_theta_ref = []
        self._mpc_theta_opt = []
        self._mpc_omega_ref = []
        self._mpc_omega_opt = []
        self._mpc_index = 0
        self._history = deque(maxlen=6)             # history of dt and theta, need to calculate omega over 6 q1 samples to get enough time for a reliable change.
        self._altitude: float = 0.0                 # The Pitch/Altitude above the local horizon of the telescope's current position (degrees, positive up)
        self._azimuth: float = 0.0                  # The Yaw/Azimuth at the local horizon of the telescope's current position (degrees, North-referenced, positive East/clockwise).
        self._roll: float = 0.0                     # The Roll (-180 to +180), 0=after GOTO, -ve=clockwise rotation looking down onto top of Astro mount axis.
        self._rotation: float = 0.0                 # The Field Rotation (-90 to 90), 0=after GOTO, -ve=clockwise rotation looking at celestrial south pole.
        self._declination: float = 0.0              # The declination (degrees) of the telescope's current equatorial coordinates, in the coordinate system given by the EquatorialSystem property. Reading the property will raise an error if the value is unavailable.
        self._rightascension: float = 0.0           # The right ascension (hours) of the telescope's current equatorial coordinates, in the coordinate system given by the EquatorialSystem property
        self._p_altitude: float = 0.0               # The Pirch/Altitude of the Polaris
        self._p_azimuth: float = 0.0                # The Yaw/Azimuth of the Polaris
        self._p_roll: float = 0.0                   # The Roll of the Polaris
        self._p_rotation: float = 0.0               # The Field Rotation of the Camera mounted on the Polaris
        self._p_declination: float = 0.0            # The declination (degrees) of the Polaris
        self._p_rightascension: float = 0.0         # The right ascension (hours) of the Polaris
        self._siderealtime: float = 0.0             # The local apparent sidereal time from the telescope's internal clock (hours, sidereal)
        self._aim_altitude: float = 0.0             # The Altitude of the last goto command
        self._aim_azimuth: float = 0.0              # The Azimuth of the last goto command
        self._adj_altitude: float = Config.aiming_adjustment_alt    # The Altitude adjustment to correct the aim based on past goto results
        self._adj_azimuth: float = Config.aiming_adjustment_az      # The Azimuth adjustment to correct the aim based on past goto results
        self._adj_sync_rightascension: float = 0    # The Rightascension adjustment difference between polaris and ascom
        self._adj_sync_declination: float = 0       # The Declination adjustment difference between polaris and ascom
        self._adj_sync_altitude: float = 0          # The Altitude adjustment difference between polaris and ascom
        self._adj_sync_azimuth: float = 0           # The Azimuth adjustment difference between polaris and ascom
        #
        # Telescope device rates
        #
        self._trackingrate: int = 0                 # Well-known telescope tracking rates. 0 = Sidereal tracking rate (15.041 arcseconds per second).
        self._trackingrates = [0,1,2,3]             # Returns a collection of supported DriveRates values (0=Sidereal, 1=Lunar, 2=Solar, 3=King)
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
        self._doesrefraction: bool = True           # True if the telescope or driver applies atmospheric refraction to coordinates.
        #
        # Telescope method constants
        #
        self._axisrates = [{ "Maximum":9, "Minimum":1 }] # Describes a range of rates supported by the MoveAxis(TelescopeAxes, Double) method (degrees/per second)   
        self._axis_Polaris_slewing_rates = [ 0, 0, 0 ]   # Records the Polaris move rate of the primary, seconday and tertiary axis
        self._axis_ASCOM_slewing_rates = [ 0, 0, 0 ]     # Records the ASCOM move rate of the primary, seconday and tertiary axis
        self._canmoveaxis = [ True, True, True ]         # True if this telescope can move the requested axis
        self._motorcontrollers = {
            axis: MotorSpeedController(logger, axis, self.send_msg)
            for axis in (0, 1, 2)
        }
        self._pid = PID_Controller(logger, self._motorcontrollers, loop=0.2)



    ########################################
    # POLARIS COMMUNICATIONS METHODS 
    ########################################

    # Exceptions
    # ConnectionAbortedError [WinError 1236] The network connection was aborted by the local system
    # OSError [error 22][WinError 121] The semaphore timeout period has expired

    # open connection and serve as polaris client
    async def client(self, logger: Logger):
        background_watchdog = asyncio.create_task(self._every_1s_watchdog_check())
        background_watchdog.add_done_callback(self.task_done)
        background_keepalive = asyncio.create_task(self._every_15s_send_polaris_keepalive())
        background_keepalive.add_done_callback(self.task_done)
        background_fastmove = asyncio.create_task(self.every_50ms_tick())
        background_fastmove.add_done_callback(self.task_done)
        if Config.log_performance_data == 2 and not Config.log_performance_data_test == 2:
            background_driftcheck = asyncio.create_task(self.every_2min_drift_check())
            background_driftcheck.add_done_callback(self.task_done)


        while True:
            try:
                self._connected = False             # set to true when "Polaris communication init... done"
                self._task_exception = None
                client_reader, client_writer = await asyncio.open_connection(Config.polaris_ip_address, Config.polaris_port)
                self._reader = client_reader
                self._writer = client_writer
                logger.info(f'==STARTUP== Starting Polaris Client on {Config.polaris_ip_address}:{Config.polaris_port}. ')
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
                        self._task_errorstr = f'==STARTUP== Cannot open network connection to Polaris. Connect with Polaris App. Check Wifi connection.'
                        logger.error(self._task_errorstr)
                        await asyncio.sleep(5)
                        continue
                    if e.winerror == 1225:
                        self._task_errorstr = f'==STARTUP== Network connection to Polaris was refused. Connect with Polaris App. Check Wifi connection.'
                        logger.error(self._task_errorstr)
                        await asyncio.sleep(5)
                        continue
                    if e.winerror == 1236:
                        self._task_errorstr = f'==ERROR== Network connection to Polaris lost. Use Polaris App to reconnect.'
                        logger.error(self._task_errorstr)
                        await asyncio.sleep(5)
                        continue
                    if e.winerror == 10054:
                        self._task_errorstr = f'==ERROR== Network connection to Polaris reset. Use Polaris App to reconnect.'
                        logger.error(self._task_errorstr)
                        await asyncio.sleep(5)
                        continue

                elif e.errno == 51:
                        self._task_errorstr = f'==STARTUP== Cannot open network connection to Polaris. Connect with Polaris App. Check Wifi connection.'
                        logger.error(self._task_errorstr)
                        await asyncio.sleep(5)
                        continue
                # errno = 60: Operation timed out
                # errno = 64: Host is down
                elif e.errno == 60 or e.errno == 64:
                        self._task_errorstr = f'==ERROR== Network connection to Polaris lost. Use Polaris App to reconnect.'
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

            except WatchdogError as e:
                self._task_errorstr = f'==STARTUP== Polaris not communicating. Resetting connection.'
                logger.error(self._task_errorstr)
                await asyncio.sleep(2)
                continue

    def task_done(self, task):
        # task.exception raises an exception if the task was cancelled, so only grab it if not cancelled.
        if not task.cancelled():
            # task.exception returns None if no exception
            self._task_exception = task.exception()

    async def send_msg(self, msg):
        if Config.log_polaris_protocol:
            self.logger.info(f'->> Polaris: send_msg: {msg}')
        if self._writer:
            self._writer.write(msg.encode())
            await self._writer.drain()

    async def _every_1s_watchdog_check(self):
        while True:
            try: 
                # calculate age of last 518 message
                curr_timestamp = datetime.datetime.now()
                if not self._last_518_timestamp:
                    self._last_518_timestamp = curr_timestamp
                age_of_518 = (curr_timestamp - self._last_518_timestamp).total_seconds()

                # self.logger.info(f'->> Polaris: age_of_518 is {age_of_518}s.')
                # if we dont have any updates, even after trying to restart AHRS, then reboot the connection
                if self._connected and age_of_518 > 5:
                    self._task_exception = WatchdogError("==ERROR==: No position update for over 5s. Rebooting Connection.")

                # if we dont have any updates for over 2s, then restart AHRS.
                if self._connected and age_of_518 > 2:
                    self.logger.info(f'->> Polaris: No position update for over 2s. Restarting AHRS.')
                    await self.send_cmd_520_position_updates(True)

                await asyncio.sleep(1)

            except Exception as e:
                self._task_exception = e
                break

    async def every_2min_drift_check(self):
        while True:
            try: 
                ra = self._targetrightascension
                dec = self._targetdeclination
                if self.connected:
                    await self.drift_error_test(ra,dec,duration=120)
                else:
                    await asyncio.sleep(10)
            except Exception as e:
                self._task_exception = e
                break

    async def _every_15s_send_polaris_keepalive(self):
        while True:
            try: 
                if self._connected:
                    await self.send_cmd_query_current_mode_async()
                await asyncio.sleep(15)

            except Exception as e:
                self._task_exception = e
                break

    async def every_50ms_tick(self):
        while True:
            try: 
                await self.every_50ms_counter_check()
                await asyncio.sleep(0.05)
            except Exception as e:
                self._task_exception = e
                break

    async def every_50ms_counter_check(self):
        self._every_50ms_counter += 1
        # At every log_perf_speed_interval take a measurement
        if self._every_50ms_counter >= Config.log_perf_speed_interval * 1000 / 50:

            # reset counter and store timestamps
            self._every_50ms_counter = 0

            # if we want to log performance data around speed travelled
            if (Config.log_performance_data == 3):
                curr_timestamp = datetime.datetime.now()
                last_timestamp = self._every_50ms_last_timestamp
                time = self.get_performance_data_time()
                # if we have a last recording
                if last_timestamp:
                    r_curr = self._axis_ASCOM_slewing_rates
                    r_last = self._every_50ms_last_a_rates
                    r_constant = (r_curr[0] == r_last[0] and r_curr[1] == r_last[1] and r_curr[2] == r_last[2])
                    d_ra = (self._p_rightascension - self._every_50ms_last_p_rightascension + 12) % 24 - 12
                    d_dec = (self._p_declination - self._every_50ms_last_p_declination + 180) % 360 - 180
                    d_alt = (self._p_altitude - self._every_50ms_last_p_altitude + 180) % 360 - 180
                    d_az = (self._p_azimuth - self._every_50ms_last_p_azimuth + 180) % 360 - 180
                    d_total = math.sqrt(d_alt*d_alt + d_az*d_az)
                    d_sec = (curr_timestamp - last_timestamp).total_seconds()
                    if d_sec>0:
                        self.logger.info(f",DATA3,{time:.3f},{d_sec:.2f},{r_constant},{r_curr[0]:.2f},{d_az/d_sec:.7f},{r_curr[1]:.2f},{d_alt/d_sec:.7f},{d_ra/d_sec:.7f},{d_dec/d_sec:.7f},'{deg2dms(d_total/d_sec)}'")

                # Store values for next run
                self._every_50ms_last_timestamp = curr_timestamp
                self._every_50ms_last_p_rightascension = self._p_rightascension
                self._every_50ms_last_p_declination = self._p_declination
                self._every_50ms_last_p_altitude = self._p_altitude
                self._every_50ms_last_p_azimuth = self._p_azimuth
                self._every_50ms_last_a_rates = self._axis_ASCOM_slewing_rates.copy()

    def get_performance_data_time(self):
        dt_now = datetime.datetime.now()
        if not self._performance_data_start_timestamp:
            self._performance_data_start_timestamp = dt_now
        time = (dt_now - self._performance_data_start_timestamp).total_seconds()
        return time

    def radec2altaz(self, ra, dec, inthefuture=0, epoch=ephem.J2000):
        target = ephem.FixedBody()
        target._ra = hr2rad(ra)
        target._dec = deg2rad(dec)
        target._epoch = epoch
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

    def radec_sync_reset(self):
        self._adj_sync_rightascension = 0
        self._adj_sync_declination = 0
        self._adj_sync_altitude = 0
        self._adj_sync_azimuth = 0
        return

    def altaz_polaris2ascom(self, p_alt, p_az):
        a_alt = p_alt + self._adj_sync_altitude
        a_az = p_az + self._adj_sync_azimuth
        return a_alt, a_az

    def altaz_ascom2polaris(self, a_alt, a_az):
        p_alt = a_alt - self._adj_sync_altitude
        p_az = a_az - self._adj_sync_azimuth
        return p_alt, p_az

    def radec_polaris2ascom(self, p_ra, p_dec):
        a_ra = p_ra + self._adj_sync_rightascension
        a_dec = p_dec + self._adj_sync_declination
        return a_ra, a_dec

    def radec_ascom2polaris(self, a_ra, a_dec):
        p_ra = a_ra - self._adj_sync_rightascension
        p_dec = a_dec - self._adj_sync_declination
        return p_ra, p_dec


    async def radec_ascom_sync(self, a_ra, a_dec):
        a_alt, a_az = self.radec2altaz(a_ra, a_dec)
        self.logger.info(f"->> Polaris: SYNC ASCOM   RA {hr2hms(a_ra)} Dec {deg2dms(a_dec)} good")

        if Config.sync_pointing_model==1:
            # Use RA/Dec Sync Pointing model
            p_ra = self._p_rightascension
            p_dec = self._p_declination
            offset_ra = a_ra - p_ra
            offset_dec = a_dec - p_dec
            self._adj_sync_rightascension = offset_ra
            self._adj_sync_declination = offset_dec
            self.logger.info(f"->> Polaris: SYNC POLARIS RA {hr2hms(p_ra)} Dec {deg2dms(p_dec)} bad")
            self.logger.info(f"->> Polaris: SYNC Offset  RA {hr2hms(offset_ra)} Dec {deg2dms(offset_dec)}")
        else:
            # Use Alt/Az Sync Pointing model
            p_alt = self._p_altitude
            p_az = self._p_azimuth
            offset_alt = a_alt - p_alt
            offset_az = a_az - p_az
            self._adj_sync_altitude = offset_alt
            self._adj_sync_azimuth = offset_az
            self.logger.info(f"->> Polaris: SYNC ASCOM   Alt {deg2dms(a_alt)} Az {deg2dms(a_az)} good")
            self.logger.info(f"->> Polaris: SYNC POLARIS Alt {deg2dms(p_alt)} Az {deg2dms(p_az)} bad")
            self.logger.info(f"->> Polaris: SYNC Offset  Alt {deg2dms(offset_alt)} Az {deg2dms(offset_az)}")

        self._rightascension = a_ra 
        self._declination = a_dec
        self._targetrightascension = a_ra
        self._targetdeclination = a_dec
        self._altitude = a_alt
        self._azimuth = a_az

        if Config.sync_pointing_model==0 and Config.sync_N_point_alignment:
            # Record all synctocordinates results
            dt_now = datetime.datetime.now()
            x = { "time": dt_now, "aAz": a_az, "aAlt": a_alt,  "oAz": offset_az, "oAlt": offset_alt }
            self.logger.info(f'->> Polaris: SYNC Star Align at Az {deg2dms(x["aAz"])} Alt {deg2dms(x["aAlt"])} | SyncOffset Az {deg2dms(x["oAz"])} Alt {deg2dms(x["oAlt"])}')
            key = f"{round(a_az/15)*15:3}"
            if not key in self._N_point_alignment_results:
                self._N_point_alignment_results[key] = []
            self._N_point_alignment_results[key].append(x)
            # Print past syncs out to log file
            for key in self._N_point_alignment_results:
                self.logger.info(f'->> Polaris: SYNC Star Align Summary around {key} degrees')
                for x in self._N_point_alignment_results[key]:
                    self.logger.info(f'->>     {x["time"].strftime("%H:%M:%S")} | Az {deg2dms(x["aAz"])} Alt {deg2dms(x["aAlt"])} | SyncOffset Az {deg2dms(x["oAz"])} Alt {deg2dms(x["oAlt"])}')
            # Perform the actual star alignment on the Polaris
            asyncio.create_task(self.send_cmd_star_alignment(a_alt, a_az))
            # No longer need a sync adjustment since Polaris has been aligned
            self._adj_sync_azimuth = 0
            self._adj_sync_altitude = 0


        return

    async def read_msgs(self):
        buffer = ""
        while True:
            # read protocol from Polaris, adding it to the buffer
            if self._reader:
                data = await self._reader.read(1024)
                if data:
                    buffer += data.decode()

            # raise any subtask exceptions so polaris.client can pick them up
            if  self._task_exception:
                raise self._task_exception
                   
            # parse all the messages in the buffer
            while buffer:
                cmd, args, buffer = self.parse_msg(buffer)
                if cmd:
                    if Config.log_polaris_protocol and not((cmd == "518" or cmd == "284" or cmd == "525") and Config.supress_polaris_frequent_msgs):
                        self.logger.info(f'<<- Polaris: recv_msg: {cmd}@{args}#')
                    self.polaris_parse_cmd(cmd, args)
            else:
                # dont overload the platform trying to read data from polaris too quickly
                await asyncio.sleep(0.05)

    # Parse a buffer returning a matched (cmd, args, remainingbuffer) or a cleared remaining buffer (False, False, "")
    def parse_msg(self, buffer):
        m = self._polaris_msg_re.match(buffer)
        if m:
            return (m.group(1), m.group(2), buffer[len(m.group(0)):])
        else:
            if Config.log_polaris and Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: Unmatched msg: {buffer}")
            return (False, False, "")

    def polaris_parse_args(self, args_str, name_postfix=False):
        # chop the last ";" and split
        postfix = 0
        args = args_str[:-1].split(";")
        arg_dict = {}
        for arg in args:
            (name, value) = arg.split(":", 1)
            if name_postfix and name in ['w', 'x', 'y', 'z']:
                postfix = postfix + 1 if name == 'w' else postfix
                name = f"{name}{postfix}"
            arg_dict[name] = value
        return arg_dict

    def polaris_parse_cmd(self, cmd, args):
        # return result of MODE request {} 
        if cmd == "284":
            arg_dict = self.polaris_parse_args(args)
            self._lock.acquire()
            self._current_mode = int(arg_dict['mode'])
            if not Config.advanced_tracking:        # if we are not doing tracking then update tracking status based on what Benro tells us 
                self._tracking = bool(arg_dict['track'] == '1') if 'track' in arg_dict else False
            self._lock.release()
            if Config.log_polaris and not Config.supress_polaris_frequent_msgs:
                self.logger.info(f"<<- Polaris: MODE status changed: {cmd} {arg_dict}")
            if cmd in self._response_queues:
                self._response_queues[cmd].put_nowait(arg_dict)

        # return result of Query Orientation request {} 
        if cmd == "517":
            arg_dict = self.polaris_parse_args(args)
            # Orientation of each axis motor rotational position in radians
            # Typical Park Position yaw=-0.000280, pitch=0.000267, roll=0.000375
            # yaw   = axis1 E rotation in radians (-2pi=-360, -pi=-180, 0=Park, pi=180;, 2pi=360, 3pi=540, etc.)
            # pitch = axis2 down rotation in radians (-0.6144=highest/83d00'37", 0=Park/47d46'06", 0.834020=0d, 0.914842=lowest/-04d38'04")
            # roll  = axis3 cw rotation in radians (-2pi=-360, -pi=-180, 0=Park, pi=180;, 2pi=360, 3pi=540', etc.)
            self.logger.info(f"<<- Polaris: GET ORIENTATION results: {cmd} {arg_dict}")

        # return result of POSITION update from AHRS {} 
        elif cmd == "518":
            dt_now = datetime.datetime.now()
    
            # extract the quaternion, angles and velocities
            arg_dict = self.polaris_parse_args(args, name_postfix=True)
            q1 = Quaternion(arg_dict['w1'], arg_dict['x1'], arg_dict['y1'], arg_dict['z1'])
            theta1, theta2, theta3, az, alt, p_roll = quaternion_to_angles(q1)
            theta_meas = [theta1, theta2, theta3]
            self._history.append([dt_now, theta1, theta2, theta3])          # deque collection, so it automatically throws away stuff older than 6 samples ago
            omega_meas = calculate_angular_velocity(self._history)
            omega_ref = [controller.rate_dps for controller in self._motorcontrollers.values()]

            
            self._kf.predict(omega_ref)
            self._kf.observe(theta_meas, omega_meas)
            theta_state, omega_state = self._kf.get_state()

            p_az = float(arg_dict['compass'])   # override filtered az with raw value from Polaris
            p_alt = -float(arg_dict['alt'])     # override filtered alt with raw value from Polaris
            p_ra, p_dec = self.altaz2radec(p_alt, p_az)

            if not is_angle_same(az, p_az):
                self.logger.warn(f"Kinematics variance p_az {p_az:.5f} az {az:.5f} diff {p_az - az:.5f} ")              
            if not is_angle_same(alt, p_alt):
                self.logger.warn(f"Kinematics variance p_alt {p_alt:.5f} alt {alt:.5f} diff {p_alt - alt:.5f}") 

            time = self.get_performance_data_time()
            if Config.log_performance_data == 5:
                [ θ1, θ2, θ3 ] = theta_meas
                [ ω1, ω2, ω3 ] = omega_meas
                [ rω1, rω2, rω3 ] = omega_ref
                [ sθ1, sθ2, sθ3 ] = theta_state
                [ sω1, sω2, sω3 ] = omega_state
                self.logger.info(f',DATA5,{time:.4f},  {p_az:+.4f},{p_alt:+.4f},{p_roll:+.4f},  {θ1:+.4f},{θ2:+.4f},{θ3:+.4f},  {sθ1:+.4f},{sθ2:+.4f},{sθ3:+.4f},  {ω1:+.5f},{ω2:+.5f},{ω3:+.5f}, {sω1:+.5f},{sω2:+.5f},{sω3:+.5f},  {rω1:+.5f},{rω2:+.5f},{rω3:+.5f} ')

            # update the PID loop
            self._pid.measure(theta_meas, np.array([az, alt, p_roll]))

            # Store all the new values
            self._lock.acquire()
            self._last_518_timestamp = dt_now
            self._q1 = q1
            self._theta_meas = theta_meas
            self._omega_meas = omega_meas
            self._p_altitude = p_alt
            self._p_azimuth = p_az
            self._p_roll = p_roll
            self._p_rotation = theta3
            self._p_rightascension = p_ra 
            self._p_declination = p_dec
            self._lock.release()

            if Config.sync_pointing_model==1:
                # Use RA/Dec Sync Pointing model
                a_ra, a_dec = self.radec_polaris2ascom(p_ra, p_dec)
                self._rightascension = a_ra 
                self._declination = a_dec
                a_alt, a_az = self.radec2altaz(a_ra, a_dec)
                self._altitude = a_alt
                self._azimuth = a_az
                self._roll = p_roll
                self._rotation = theta3
            else:
                # Use Alt/Az Sync Pointing model
                a_alt, a_az = self.altaz_polaris2ascom(p_alt, p_az)
                self._altitude = a_alt
                self._azimuth = a_az
                self._roll = p_roll
                self._rotation = theta3
                a_ra, a_dec= self.altaz2radec(a_alt, a_az)
                self._rightascension = a_ra 
                self._declination = a_dec

            # if we ant to log position data
            if Config.log_performance_data == 4:
                a_slew = self._slewing
                a_goto = self._gotoing
                a_track = self.tracking
                t_ra = self._targetrightascension if self._targetrightascension else a_ra       # Target Right Ascention (hours)
                t_dec = self._targetdeclination if self._targetdeclination else a_dec           # Target Declination (degrees)
                e_ra = clamparcsec((t_ra - a_ra)*3600*360/24)                                   # Error Right Ascention (arc seconds)
                e_dec = clamparcsec((t_dec - a_dec)*3600)                                       # Error Declination (arc seconds)
                time = self.get_performance_data_time()
                self.logger.info(f",DATA4,{time:.3f},{a_track},{a_slew},{a_goto},{t_ra:.7f},{t_dec:.7f},{a_ra:.7f},{a_dec:.7f},{a_az:.7f},{a_alt:.7f},{e_ra:.3f},{e_dec:.3f}")

        # return result of GOTO request {'ret': 'X', 'track': '1'}  X=1 (starting slew), X=2 (stopping slew)
        elif cmd == "519":
            arg_dict = self.polaris_parse_args(args)
            if cmd in self._response_queues:
                self._response_queues[cmd].put_nowait(arg_dict)

        # return result of UNKNOWN command SP_SendMsgToApp success;type[2],code[525],val[Tempa509ca361d0000265a ;]
        elif cmd == "525":
            if Config.log_polaris and not Config.supress_polaris_frequent_msgs:
                self.logger.info(f"<<- Polaris: 525 status changed: {cmd} {args}")

        # return result of TRACK change request {'ret': 'X'} where X=0 (NoTracking), X=1 (Tracking)
        elif cmd == "531":
            arg_dict = self.polaris_parse_args(args)
            self._lock.acquire()
            if not Config.advanced_tracking:     # if we are not doing tracking then update tracking status based on what Benro tells us 
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

        # return result of Connection request result {'ret': '0'}
        elif cmd == "808":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris and Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: Connection request result: {cmd} {arg_dict}")

        # return result of Position Updaten request result {'ret': '1'}
        elif cmd == "520":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris and Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: Position Update request result: {cmd} {arg_dict}")


        # return result of unrecognised msg
        else:
            if Config.log_polaris and not Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: response to command received: {cmd} {args}")


    def aim_altaz_log_result(self):
        self._lock.acquire()
        a_alt = self._aim_altitude
        a_az = self._aim_azimuth
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
        time = self.get_performance_data_time()
        self.logger.info(f"->> Polaris: GOTO AimOffset (Az {deg2dms(adj_az)} Alt {deg2dms(adj_alt)}) | Error Az {err_az*3600:.3f} Alt {err_alt*3600:.3f}")
        # if we want to log Aim data
        if Config.log_performance_data == 1:
            self.logger.info(f",DATA1,{time:.3f},{a_az:.7f},{a_alt:.7f},{adj_az:.7f},{adj_alt:.7f},{err_az*3600:.3f},{err_alt*3600:.3f}")

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

    # Abort Slew
    # eg state:0;yaw:0.0;pitch:0.0;lat:-33.655422;track:0;speed:0;lng:151.12244;
    async def send_cmd_goto_abort(self):
        self._lock.acquire()
        self._slewing = False
        self._gotoing = False
        self._lock.release()
        # log the command
        if Config.log_polaris:
            self.logger.info(f"->> Polaris: GOTO ABORT")
        arg_dict = {'ret': '-1', 'track': '-1'}
        cmd = '519'
        msg = f"1&{cmd}&3&state:0;yaw:0.0;pitch:0.0;lat:{self._sitelatitude:.5f};track:0;speed:0;lng:{self._sitelongitude:.5f};#"
        await self.send_msg(msg)
        self._response_queues[cmd].put_nowait(arg_dict)
        self._response_queues[cmd].put_nowait(arg_dict)

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
            self.logger.info(f"->> Polaris: GOTO Execute Alt {deg2dms(alt)} Az {deg2dms(az)} ")

        # log the aiming alt/az and correct it based on previous aiming results
        calt, caz = self.aim_altaz_log_and_correct(alt, az)

        # turn off tracking before we issue the cmd
        await self.stop_tracking()

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

        # log the result of the goto if it was NOT aborted and is a tracking GOTO
        if (not (ret_dict["ret"] == '-1')) and istracking:
            self.aim_altaz_log_result()

        return ret_dict

    async def send_cmd_reset_axis(self, axis:int):
        if axis==1 or axis==2 or axis==3:
            await self.send_msg(f"1&523&3&axis:{axis};#")

    async def send_cmd_compass_alignment(self, angle:float = None):
        # use angle provided or assume synced ASCOM azimuth
        a_az = angle if angle else self._azimuth
        compass = (a_az - 180.0) % 360
        lat = self._sitelatitude
        lon = self._sitelongitude
        self._adj_sync_azimuth = 0
        await self.send_msg(f"1&527&3&compass:{compass};lat:{lat};lng:{lon};#")

    async def send_cmd_star_alignment(self, a_alt:float, a_az:float):
        lat = self._sitelatitude
        lon = self._sitelongitude
        ca_az = 360 - a_az if a_az>180 else -a_az
        # Do we even need to GOTO Star since we are already pointing at it?
        # await self.send_cmd_goto_altaz(self._p_altitude, self._p_azimuth, istracking=False)   
        await self.send_msg(f"1&530&3&step:1;yaw:0.0;pitch:0.0;lat:0.0;num:0;lng:0.0;#")
        await asyncio.sleep(2)
        await self.send_msg(f"1&530&3&step:2;yaw:{ca_az};pitch:{a_alt};lat:{lat};num:1;lng:{lon};#")
        await asyncio.sleep(0.2)
        await self.send_msg(f"1&530&3&step:3;yaw:0.0;pitch:0.0;lat:0.0;num:0;lng:0.0;#")

    async def send_cmd_park(self):
        if Config.log_polaris:
            self.logger.info(f"->> Polaris: PARK all 3 axis")
        await self.send_cmd_reset_axis(1)
        await self.send_cmd_reset_axis(2)
        await self.send_cmd_reset_axis(3)

    async def send_cmd_query_current_mode(self):
        if Config.log_polaris:
            self.logger.info(f"->> Polaris: MODE query status info request")
        cmd = '284'
        msg = f"1&{cmd}&2&-1#"
        empty_queue(self._response_queues[cmd])
        await self.send_msg(msg)
        ret_dict = await self._response_queues[cmd].get()
        return ret_dict

    async def send_cmd_query_current_mode_async(self):
        if Config.log_polaris and not Config.supress_polaris_frequent_msgs:
            self.logger.info(f"->> Polaris: 284 Query Mode request")
        msg = f"1&284&2&-1#"
        await self.send_msg(msg)

    async def send_cmd_799(self):
        if Config.log_polaris and Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 799 request")
        msg = f"1&799&2&-1#"
        await self.send_msg(msg)

    async def send_cmd_296(self):
        if Config.log_polaris and Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 296 request")
        msg = f"1&296&2&-1#"
        await self.send_msg(msg)

    async def send_cmd_303(self):
        if Config.log_polaris and Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 303 request")
        msg = f"1&303&2&-1#"
        await self.send_msg(msg)

    async def send_cmd_808(self):
        if Config.log_polaris and Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 808 Connection request")
        msg = f"1&808&2&type:0;#"
        await self.send_msg(msg)

    async def send_cmd_517(self):
        if Config.log_polaris and Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 517 Get Orientation request")
        msg = f"1&517&3&-1#"
        await self.send_msg(msg)

    async def send_cmd_520_position_updates(self, state:bool=True):
        state = "1" if state else "0"
        if Config.log_polaris and Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 520 Position Updates request")
        msg = f"1&520&2&state:{state};#"
        await self.send_msg(msg)

    async def send_cmd_524(self):
        if Config.log_polaris and Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 524 request")
        msg = f"1&524&3&-1#"
        await self.send_msg(msg)

    async def send_cmd_305(self):
        if Config.log_polaris and Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 305 request")
        msg = f"1&305&2&step:2;#"
        await self.send_msg(msg)

    async def send_cmd_780(self):
        if Config.log_polaris and Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 780 request")
        msg = f"1&780&2&-1#"
        await self.send_msg(msg)


    async def polaris_init(self):
        self.logger.info("Polaris communication init...")
        ret_dict = await self.send_cmd_query_current_mode()
        if  'mode' in ret_dict and int(ret_dict['mode']) == 8:
            if 'track' in ret_dict and int(ret_dict['track']) == 3:
                # Polaris is in astro mode but alignment not complete
                raise AstroAlignmentError()
            s_lat = self._sitelatitude
            s_lon = self._sitelongitude
            self.logger.info("Polaris communication init... done")
            self.logger.info(f'Site lat = {s_lat} ({deg2dms(s_lat)}) | lon = {s_lon} ({deg2dms(s_lon)}).')
            self.logger.warn(f'Change site_latitude and site_longitude in config.toml or use Nina/StellariumPLUS to sync.')
            # await self.send_cmd_799()
            # await self.send_cmd_296()
            # await self.send_cmd_303()
            await self.send_cmd_808()
            await self.send_cmd_520_position_updates(True)
            # await self.send_cmd_524()
            # await self.send_cmd_305()
            # await self.send_cmd_780()
            self._lock.acquire()
            self._connected = True
            self._task_errorstr = ''
            self._lock.release()
            # if we want to run Aim test or Drift test over a set of targets in the sky
            if Config.log_performance_data_test == 1 or Config.log_performance_data_test == 2:
                asyncio.create_task(self.goto_tracking_test())
            # if we want to run Speed test to ramp moveaxis rate over its full range
            if Config.log_performance_data_test == 3:
                asyncio.create_task(self.moveaxis_speed_calibration_full_test())
            if Config.log_performance_data_test == 5:
                asyncio.create_task(self.rotator_test())
        else:
            # Polaris is not in astro mode
            raise AstroModeError()


    async def rotator_test(self):
        if self._test_underway:
            return
        self._test_underway = True
        Config.log_performance_data == 0
        axis = 2 # Rotation
        steps = 8
        duration = 90.0/4
        self.logger.info(f"== TEST == Rotator Test | {steps} steps")
        for i in range(0, steps, 1):
            alt = 10 + 80/steps * i
            az = 180
            await self.send_cmd_goto_altaz(alt, az, False)
            self.logger.info(f"== TEST == Rotator Test | {alt:.2f} alt")
            Config.log_performance_data = 5
            await self.move_axis(2, 9)
            await asyncio.sleep(duration)
            Config.log_performance_data = 0
            await self.move_axis(2, 0)
            await asyncio.sleep(2)
        # complete the test
        self.logger.info(f"== TEST == Rotator Test | COMPLETE")


    async def moveaxis_speed_calibration_full_test(self):
        if self._test_underway:
            return
        self._test_underway = True

        results = {}
        for axis in [0,1,2]:
            results[axis] = (await self.moveaxis_slow_fast_calibration_test(axis))

        formatted_results = format_move_axis_data(results)
        self.logger.info(f'== TEST == Multi-Axis Calibration COMPLETE\n{formatted_results}')
        self._test_underway = False

    async def moveaxis_slow_fast_calibration_test(self, axis):
        raw_rates = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0] 
        raw_rates += [0.0] + [x for x in range(200,500,100)] + [x for x in range(500,2500+250,250)]
        results = []
        direction = +1
        # Ramp through the raw rates
        for rate in raw_rates:
            if axis==1 and self._theta_meas:
                if self._theta_meas[1] > 60:
                    await self.move_axis(axis, 0)
                    await asyncio.sleep(3)
                    direction = -1
                if self._theta_meas[1] < 20:
                    await self.move_axis(axis, 0)
                    await asyncio.sleep(3)
                    direction = +1

            await self.move_axis(axis, rate * direction, "RAW")
            result = await self.moveaxis_speed_measurement(axis, rate)
            results.append(result)

        await self.move_axis(axis, 0)
        await asyncio.sleep(3)

        mid = results[5][0]
        max = results[-1][0]
        interp = PchipInterpolator([0, mid, 0.18*max, 0.5*max, max], [0,5,6,7,9], extrapolate=True)
        summary = { 'RAW':[], 'DPS':[], 'ASCOM':[], 'STDEV':[], 'BAD':[] }
        for result in results:
            summary['DPS'].append(result[0])
            summary['RAW'].append(result[1])
            summary['STDEV'].append(result[2])
            summary['BAD'].append(result[3])
            summary['ASCOM'].append(interp(result[0]) if result[1] > 5 else result[1])
        
        return summary

      

    async def moveaxis_speed_measurement(self, axis, rate, required_stable_samples = 5, initial_interval = 3.0, max_interval = 15, sampling_interval = 0.25):
        start_time = time.monotonic()
        stable_tolerance = 0.05 if rate > 5 else 0.0005
        await asyncio.sleep(initial_interval)
        rate_raw = self._motorcontrollers[axis].rate_raw    # what the controller thinks the raw rate is
        rate_dps = self._motorcontrollers[axis].rate_dps    # what the controller thinks the dps rate is
        status = "OK"

        omega_samples = []     # deg/sec
        while time.monotonic() - start_time < max_interval:
            await asyncio.sleep(sampling_interval)
            omega = self._omega_meas[axis]
            omega_samples.append(omega)

            # if we potentially have enough samples, take a window the last set
            if len(omega_samples) >= required_stable_samples:
                window = omega_samples[-required_stable_samples:]
                stdev = np.std(window)
                if stdev < stable_tolerance and (np.mean(window) > 0.002 or rate == 0):
                    measured_dps = float(np.mean(window)) if rate>0 else 0
                    self.logger.info(f"== TEST == Stable | Axis {axis} |  RAW {rate_raw} | DPS: {measured_dps:.5f}, stdev: {stdev:.7f}, last 5 of {len(omega_samples)}")
                    break
        # exited while without a value in tollerance
        else:
            measured_dps = rate_dps  # fallback to the controller's rate
            status = "UNSTABLE"
            self.logger.info(f'== TEST == **UNSTABLE** on Axis {axis} |  RAW {rate_raw} | stdev: {stdev:.7f}, last 5 of {len(omega_samples)}')
        return abs(measured_dps), abs(rate_raw), stdev, status


    async def goto_tracking_test(self):
        if self._test_underway:
            return
        self._test_underway = True
        nRA = int(360/30)
        nDec = int(180/15)
        await asyncio.sleep(30)             # Start test 30s after startup
        for j in range(0, nDec, 1):
            for i in range(0, nRA, 1):
                e_ra = i/nRA*24
                e_dec = j/nDec*180-90 if self._sitelatitude<0 else (nDec - j)/nDec*180-90
                if (abs(e_dec)==90 and e_ra!=0):    # only do it once at the poles
                    continue
                now_coord = ephem.Equatorial(hr2rad(e_ra), deg2rad(e_dec), epoch=ephem.now())
                radec = ephem.Equatorial(now_coord, epoch=ephem.J2000)
                a_ra=rad2hr(radec.ra)
                a_dec=rad2deg(radec.dec)
                p_ra, p_dec = self.radec_ascom2polaris(a_ra, a_dec)
                p_alt, p_az = self.radec2altaz(p_ra, p_dec)
                if p_alt>12 and p_alt<80:           # only GOTO if within range of Benro Polaris capabilities
                    self.logger.info(f"== TEST == GOTO Tracking Test | Now RA {e_ra:5.1f} Dec {e_dec:5.1f} | J2000 RA {a_ra:5.1f} Dec {a_dec:5.1f} | Az {p_az:5.1f} Alt {p_alt:5.1f}")
                    await self.SlewToCoordinates(a_ra, a_dec, isasync = False)
                    # if we want to do Aim test (assumes Aim Data is being logged), just pause
                    if Config.log_performance_data_test == 1:
                        await asyncio.sleep(5)
                    # if we want to do Drift test, await for it to perform a single test
                    if Config.log_performance_data_test == 2:
                        await self.drift_error_test(e_ra, e_dec, duration=3*60)

    async def drift_error_test(self, ra, dec, duration=120):
        a0_ra = self._rightascension
        a0_dec = self._declination
        a0_track = self.tracking
        t0 = datetime.datetime.now()
        await asyncio.sleep(duration)
        a1_ra = self._rightascension
        a1_dec = self._declination
        a1_track = self.tracking
        t1 = datetime.datetime.now()
        d_t = (t1 - t0).total_seconds()
        d_ra = clamparcsec((a0_ra - a1_ra)*3600/24*360)/d_t*60
        d_dec = clamparcsec((a0_dec - a1_dec)*3600)/d_t*60
        a_ra = ra if ra else self._targetrightascension if self._targetrightascension else self._rightascension
        a_dec = dec if dec else self._targetdeclination if self._targetdeclination else self._declination
        time = self.get_performance_data_time()
        self.logger.info(f",DATA2,{time:.3f},{a0_track},{a1_track},{a_ra},{a_dec},{d_ra:.3f},{d_dec:.3f}")
        return


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
    def roll(self) -> float:
        self._lock.acquire()
        res =  self._roll
        self._lock.release()
        return res

    @property
    def rotation(self) -> float:
        self._lock.acquire()
        res =  self._rotation
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
        self._observer.lat = deg2rad(sitelatitude) 
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
        self._observer.long = deg2rad(sitelongitude) 
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
        self._observer.pressure = Config.site_pressure if doesrefraction else 0
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

    async def SlewToAltAz(self, altitude, azimuth, isasync = True) -> None:
        a_alt = altitude
        a_az = azimuth
        a_ra, a_dec = self.altaz2radec(a_alt, a_az)
        self.logger.info(f"->> Polaris: GOTO ASCOM   Alt: {deg2dms(a_alt)} Az: {deg2dms(a_az)}")
        await self.SlewToCoordinates(a_ra, a_dec, isasync)

    # ******* Advanced MPC control aware methods ********

    async def SlewToCoordinates(self, rightascension, declination, isasync = True) -> None:
        a_ra = rightascension
        a_dec = declination
        self._lock.acquire()
        self._targetrightascension = a_ra
        self._targetdeclination = a_dec
        self._lock.release()
        inthefuture = Config.aiming_adjustment_time if Config.aiming_adjustment_enabled else 0
        if Config.sync_pointing_model==1:
            # Use RA/Dec Sync Pointing model
            p_ra, p_dec = self.radec_ascom2polaris(a_ra, a_dec)
            o_ra = self._adj_sync_rightascension
            o_dec = self._adj_sync_declination
            p_alt, p_az = self.radec2altaz(p_ra, p_dec, inthefuture)
            self.logger.info(f"->> Polaris: GOTO ASCOM   RA {hr2hms(a_ra)} Dec {deg2dms(a_dec)}")
            self.logger.info(f"->> Polaris: GOTO POLARIS RA {hr2hms(p_ra)} Dec: {deg2dms(p_dec)} | SyncOffset (RA {deg2dms(o_ra)} Dec {deg2dms(o_dec)})")
        else:
            # Use Alt/Az Sync Pointing model
            a_alt, a_az = self.radec2altaz(a_ra, a_dec, inthefuture)
            p_alt, p_az = self.altaz_ascom2polaris(a_alt, a_az)
            o_alt = self._adj_sync_altitude
            o_az = self._adj_sync_azimuth
            self.logger.info(f"->> Polaris: GOTO ASCOM   RA {hr2hms(a_ra)} Dec {deg2dms(a_dec)}")
            self.logger.info(f"->> Polaris: GOTO ASCOM   Alt {deg2dms(a_alt)} Az {deg2dms(a_az)}")
            self.logger.info(f"->> Polaris: GOTO POLARIS Alt {deg2dms(p_alt)} Az {deg2dms(p_az)} | SyncOffset (Alt {deg2dms(o_alt)} Az {deg2dms(o_az)})")

        if Config.advanced_control and Config.advanced_goto:
            self.logger.info(f"->> Advanced Contro: GOTO Alt {deg2dms(p_alt)} Az {deg2dms(p_az)} | SyncOffset (Alt {deg2dms(o_alt)} Az {deg2dms(o_az)})")
            self._pid.set_alpha_target(np.array([p_az, p_alt, 0]))
        else:
            if isasync:
                    asyncio.create_task(self.send_cmd_goto_altaz(p_alt, p_az, istracking=True))
            else:
                await self.send_cmd_goto_altaz(p_alt, p_az, istracking=True)

    async def AbortSlew(self):
        if Config.advanced_control and Config.advanced_goto:
            self.logger.info(f"Advanced Control: ABORT GOTO")
            await self.stop_all_axes()
        else:
            await self.send_cmd_goto_abort()


    async def move_axis(self, axis:int, rate:float, units="ASCOM"):
        if Config.advanced_control and Config.advanced_slewing:
            raw = self._motorcontrollers[axis]._model.interpolate[units].toRAW(rate)
            dps = self._motorcontrollers[axis]._model.interpolate["RAW"].toDPS(raw)
            self._pid.set_alpha_axis_velocity(axis, dps)
        else:
            self.logger.info(f"->> Polaris: MOVE Az/Alt/Rot Axis {axis} Rate {rate} Units {units}")
            if not self._tracking:
                await self._motorcontrollers[axis].set_motor_speed(rate, units)

    async def stop_all_axes(self):
        if Config.advanced_control:
            self.logger.info(f"Advanced Control: STOP all axes")
            self._pid.mode = "IDLE"
            self._pid.is_moving = False
        await self._motorcontrollers[0].set_motor_speed(0, "DPS")
        await self._motorcontrollers[1].set_motor_speed(0, "DPS")
        await self._motorcontrollers[2].set_motor_speed(0, "DPS")

    async def stop_tracking(self):
        if Config.advanced_control and Config.advanced_tracking:
            self.logger.info(f"Advanced Control: STOP tracking")
            self._tracking = False
            self._pid.is_tracking = False
        else:
            # only send message if we are already tracking
            if self._tracking:
                self._tracking = False
                await self.send_cmd_change_tracking_state(False)

    async def start_tracking(self):
        if Config.advanced_control and Config.advanced_tracking:
            self.logger.info(f"Advanced Control: START tracking")
            self._tracking = True
            self._pid.is_tracking = True
        else:
            # only send message if we are not tracking and not slewing
            if not self._tracking and not self._slewing:
                self._tracking = True
                await self.send_cmd_change_tracking_state(True)

    async def park(self):
        self._lock.acquire()
        self._atpark = True
        self._adj_sync_declination = 0
        self._adj_sync_rightascension = 0
        self._adj_altitude = 0
        self._adj_azimuth = 0
        self._lock.release()
        if Config.advanced_control:
            self.logger.info(f"Advanced Control: PARK telescope")
            await self.stop_all_axes()
            await asyncio.sleep(2)
            await self.send_cmd_park()
        else:
            await self.stop_tracking()
            await asyncio.sleep(1)
            await self.send_cmd_park()

    async def unpark(self):
        self._lock.acquire()
        self._atpark = False
        self._lock.release()

