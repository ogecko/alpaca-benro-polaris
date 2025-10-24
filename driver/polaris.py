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
import logging
import numpy as np
from collections import deque
from pyquaternion import Quaternion
from threading import Lock
from logging import Logger
from config import Config
from exceptions import AstroModeError, AstroAlignmentError, WatchdogError
from shr import deg2rad, rad2hr, rad2deg, hr2rad, deg2dms, hr2hms, bytes2hexascii, clamparcsec, empty_queue, LifecycleController, LifecycleEvent
from control import quaternion_to_angles, motors_to_quaternion, calculate_angular_velocity, is_angle_same, wrap_to_360
from control import KalmanFilter, CalibrationManager, MotorSpeedController, PID_Controller, SyncManager
from ble_service import BLE_Controller

POLARIS_POLL_COMMANDS = {'284', '518', '525'}


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
    def __init__(self, logger: Logger, lifecycle: LifecycleController):
        self._lock = Lock()
        self.name: str = 'device'
        self.logger: Logger = logger
        self.lifecycle: LifecycleController = lifecycle
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
        self._polaris_mode = -1                     # Current Mode of the Polaris Device (1=Photo, 2=Pano, 3=Focus, 4=Timelapse, 5=Pathlapse, 6=HDR, 7=Sun, 8=**Astro**, 9=Program, 10=Video )
        self._polaris_msg_re = re.compile(r'(\d{3})@(.+?)#')
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
        self._sitepressure: float = float(Config.site_pressure)     # The pressure above mean sea level (meters) of the site at which the telescope is located
        self._observer = ephem.Observer()                           # Observer object for the telescopes site
        self._observer.pressure = float(Config.site_pressure)       # site pressure used for refraction calculations close to horizon
        self._observer.epoch = ephem.J2000                          # a moment in time used as a reference point for RA/Dec
        self._observer.lat = deg2rad(self._sitelatitude)            # dms version on lat
        self._observer.long = deg2rad(self._sitelongitude)          # dms version of long
        self._observer.elevation = float(self._siteelevation)       # site elevation
        #
        # Polaris status variables
        self._battery_is_available: bool = False    # Is the Polaris battery status current
        self._battery_is_charging: bool = False     # Is the Polaris device currently charging
        self._battery_level: int = 100              # Battery level of the Polaris device (percentage)
        self._polaris_sw_ver: str = ''              # Polaris Software Version
        self._polaris_hw_ver: str = ''              # Polaris Hardware Version
        #
        # Telescope device completion flags
        #
        self._connections = {}                      # Dictionary of client's connection status True/False
        self._compassed: bool = False               # Polaris alignment status. True if compass alignment performed. 
        self._aligned: bool = False                 # Polaris alignment status. True if one star alignment performed. 
        self._aligning: bool = False                # Polaris is in the process of aligning single star. 
        self._connected: bool = False               # Polaris connection status. True if any client is connected. False when all clients have left.
        self._connecting: bool = False              # Polaris is in the process of connecting. 
        self._tracking: bool = False                # The state of the ASCOM telescope's sidereal tracking drive.
        self._tracking_in_benro: bool = False       # The state of the Benro Polaris tracking mode.
        self._sideofpier: int = -1                  # Indicates the pointing state of the mount. Unknown = -1
        self._athome: bool = False                  # True if the telescope is stopped in the Home position. Set only following a FindHome() operation, and reset with any slew operation. This property must be False if the telescope does not support homing.
        self._atpark: bool = False                  # True if the telescope has been put into the parked state by the seee Park() method. Set False by calling the Unpark() method.
        self._slewing: bool = False                 # True if telescope is in the process of moving in response to one of the Goto methods or the MoveAxis(TelescopeAxes, Double) method, False at all other times.
        self._gotoing: bool = False                 # True if telescope is in the process of moving in response to one of the Goto methods, False at all other times.
        self._rotating: bool = False                # True if rotator is in the process of moving 
        self._goto_complete_event = None            # asyncio Event to allow notification of goto complete (only used with advanced control gotos)
        self._rotate_complete_event = None          # asyncio Event to allow notification of rotate complete (only used with advanced control rotates)
        self._slew_complete_event = None            # asyncio Event to allow notification of slew complete (only used with advanced control rotates)
        self._ispulseguiding: bool = False          # True if a PulseGuide(GuideDirections, Int32) command is in progress, False otherwise
        #
        # Telescope device state variables
        #
        self._altitude: float = 0.0                 # The Pitch/Altitude above the local horizon of the telescope's current position (degrees, positive up)
        self._azimuth: float = 0.0                  # The Yaw/Azimuth at the local horizon of the telescope's current position (degrees, North-referenced, positive East/clockwise).
        self._roll: float = 0.0                     # The Roll (-180 to +180), 0=after GOTO, -ve=clockwise rotation looking down onto top of Astro mount axis.
        self._rotation: float = 0.0                 # The Field Rotation (-90 to 90), 0=after GOTO, -ve=clockwise rotation looking at celestrial south pole.
        self._declination: float = 0.0              # The declination (degrees) of the telescope's current equatorial coordinates, in the coordinate system given by the EquatorialSystem property. Reading the property will raise an error if the value is unavailable.
        self._rightascension: float = 0.0           # The right ascension (hours) of the telescope's current equatorial coordinates, in the coordinate system given by the EquatorialSystem property
        self._parallactic_angle: float = 0.0         # The current parallactic angle of the telescope (degrees, -180 to +180)
        self._position_angle: float = 0.0            # The current position angle of the telescope (degrees, 0 to 360)
        self._p_altitude: float = 0.0               # The Pirch/Altitude of the Polaris
        self._p_azimuth: float = 0.0                # The Yaw/Azimuth of the Polaris
        self._p_roll: float = 0.0                   # The Roll of the Polaris
        self._p_declination: float = 0.0            # The declination (degrees) of the Polaris
        self._p_rightascension: float = 0.0         # The right ascension (hours) of the Polaris
        self._siderealtime: float = 0.0             # The local apparent sidereal time from the telescope's internal clock (hours, sidereal)
        self._aim_altitude: float = 0.0             # The Altitude of the last goto command
        self._aim_azimuth: float = 0.0              # The Azimuth of the last goto command
        self._adj_altitude: float = Config.aiming_adjustment_alt    # The Altitude adjustment to correct the aim based on past goto results
        self._adj_azimuth: float = Config.aiming_adjustment_az      # The Azimuth adjustment to correct the aim based on past goto results
        self._adj_sync_altitude: float = 0          # The Altitude adjustment difference between polaris and ascom
        self._adj_sync_azimuth: float = 0           # The Azimuth adjustment difference between polaris and ascom
        #
        # Telescope device rates
        #
        self._trackingrate: int = 0                 # Well-known telescope tracking rates. 0 = Sidereal tracking rate (15.041 arcseconds per second).
        self._trackingrates = [0,1,2,3]             # Returns a collection of supported DriveRates values (0=Sidereal, 1=Lunar, 2=Solar, 3=King)
        self._declinationrate: float = 0.0          # The declination tracking rate (arcseconds per SI second, default = 0.0)
        self._rightascensionrate: float = 0.0       # The right ascension tracking rate offset from sidereal (seconds per sidereal second, default = 0.0)
        self._guideratedeclination: float = 0.002089     # The current Declination movement rate offset for telescope guiding, default 0.5 x sidereal (degrees/sec)
        self._guideraterightascension: float = 0.002089  # The current Right Ascension movement rate offset for telescope guiding, default 0.5 x sidereal (degrees/sec)
        #
        # Rotator device settings
        #
        self._rotator_reverse: bool = False         # Is the rotator in reverse direction.
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
        self._targetpositionangle: float = None     # The position angle (degrees) for the target of a rotator move or moveabsolute
        #
        # Telescope capability constants
        #
        self._canfindhome: bool = True             # True if this telescope is capable of programmed finding its home position (FindHome() method).
        self._canpark: bool = True                  # True if this telescope is capable of programmed parking (Park()method)
        self._canpulseguide: bool = True            # True if this telescope is capable of software-pulsed guiding (via the PulseGuide(GuideDirections, Int32) method)
        self._cansetdeclinationrate: bool = False   # True if the DeclinationRate property can be changed to provide offset tracking in the declination axis.
        self._cansetguiderates: bool = True         # True if the guide rate properties used for PulseGuide(GuideDirections, Int32) can ba adjusted.
        self._cansetpark: bool = True              # True if this telescope is capable of programmed setting of its park position (SetPark() method)
        self._cansetpierside: bool = False          # True if the SideOfPier property can be set, meaning that the mount can be forced to flip.
        self._cansetrightascensionrate: bool = False# True if the RightAscensionRate property can be changed to provide offset tracking in the right ascension axis.
        self._cansettracking: bool = True           # True if the Tracking property can be changed, turning telescope sidereal tracking on and off.
        self._canslew: bool = True                  # True if this telescope is capable of programmed slewing (synchronous or asynchronous) to equatorial coordinates
        self._canslewasync: bool = True             # True if this telescope is capable of programmed asynchronous slewing to equatorial coordinates.
        self._canslewaltaz: bool = True             # True if this telescope is capable of programmed slewing (synchronous or asynchronous) to local horizontal coordinates
        self._canslewaltazasync: bool = True        # True if this telescope is capable of programmed asynchronous slewing to local horizontal coordinates
        self._cansync: bool = True                  # True if this telescope is capable of programmed synching to equatorial coordinates.
        self._cansyncaltaz: bool = True             # True if this telescope is capable of programmed synching to local horizontal coordinates
        self._canunpark: bool = True                # True if this telescope is capable of programmed unparking (Unpark() method).
        self._doesrefraction: bool = True           # True if the telescope or driver applies atmospheric refraction to coordinates.
        #
        # Telescope method constants
        #
        self._axisrates = [{ "Maximum":9, "Minimum":1 }] # Describes a range of rates supported by the MoveAxis(TelescopeAxes, Double) method (degrees/per second)   
        self._axis_ASCOM_slewing_rates = [ 0, 0, 0 ]     # Records the ASCOM move rate of the primary, seconday and tertiary axis
        self._canmoveaxis = [ True, True, True ]         # True if this telescope can move the requested axis

        # Advanced Control variables
        self._q1 = None                             # The latest quaternion mapping Camera Co-ordinates Framework to Topocentric Co-ordinates Framework
        self._q1s = None                            # The estimated quaternion state based on Kalman Filter
        self._zeta_meas = None                      # The latest set of Polaris raw motor axis angles [zeta1, zeta2, zeta3] measured from "517"
        self._lota_meas = None                      # The latest set of Polaris 1-aligned position angle [az, alt, roll, ra, dec] measured from q1
        self._theta_meas = None                     # The latest set of Polaris 1-aligned motor axis angles [theta1, theta2, theta3] measured from q1
        self._theta_state = None                    # The state of 1-aligned motor axis angles [theta1, theta2, theta3] estimated by KF
        self._omega_meas = None                     # The latest set of Polaris motor axis angular velocity [omega1, omega2, omega3] measured from q1
        self._history = deque(maxlen=6)             # history of dt and theta, need to calculate omega over 6 q1 samples to get enough time for a reliable change.
        self._cm = CalibrationManager()
        self._kf: KalmanFilter = KalmanFilter(logger, np.zeros(6))
        self._motors = {
            axis: MotorSpeedController(logger, self._cm, axis, self.send_msg)
            for axis in (0, 1, 2)
        }
        self._pid = PID_Controller(logger, self, loop=0.2)
        self._ble = BLE_Controller(logger, lifecycle, lambda: self.connected)
        self._sm = SyncManager(logger, self)

        
    async def shutdown(self):
        self.logger.info(f'==SHUTDOWN== Polaris stopping all tasks.')
        for pid in [self._pid]:
            await pid.stop_control_loop_task()

        for axis in range(3):
            motor = self._motors[axis]
            await motor.stop_disspatch_loop_task()

    ########################################
    # POLARIS COMMUNICATIONS METHODS 
    ########################################

    # Exceptions
    # ConnectionAbortedError [WinError 1236] The network connection was aborted by the local system
    # OSError [error 22][WinError 121] The semaphore timeout period has expired

    def _format_connection_error(self, e: Exception) -> str:
        if isinstance(e, ConnectionAbortedError):
            return "The Polaris network connection was aborted."
        if isinstance(e, OSError):
            if getattr(e, 'winerror', None) == 121:
                return "Check Network. Cannot open Polaris connection."
            if getattr(e, 'winerror', None) == 1225:
                return "Connection refused. Check Polaris App and network."
            if getattr(e, 'winerror', None) == 1236:
                return "Connection lost. Reconnect via Polaris App."
            if getattr(e, 'winerror', None) == 10054:
                return "Connection reset. Reconnect via Polaris App."
            if e.errno == 51:
                return "Check Network. Cannot open Polaris connection"
            if e.errno in (60, 64):
                return "Check Hostname. Polaris host unreachable."
        if isinstance(e, AstroModeError):
            return "Polaris not in Astro Mode. Use Polaris App to change."
        if isinstance(e, AstroAlignmentError):
            return "Polaris not aligned. Complete alignment in Polaris App."
        if isinstance(e, WatchdogError):
            return "Polaris not communicating. Resetting connection."
        return f"Unexpected error: {str(e)}"


    async def attempt_polaris_disconnect(self):
        self.logger.info("==SHUTDOWN== Disconnecting Polaris...")
        # Close socket connection
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
                self.logger.info("==SHUTDOWN== Polaris socket closed.")
            except Exception as e:
                self.logger.error(f"==SHUTDOWN== Error closing socket: {e}")
        # Reset internal state
        with self._lock:
            self._connected = False
            self._connecting = False
            self._battery_is_available = False
            self._reader = None
            self._writer = None
            self._task_exception = None
            self._task_errorstr = ""

    async def attempt_polaris_connect(self):
        try:
            with self._lock:
                self._connected = False             # set to true when "Polaris communication init... done"
                self._connecting = True             # set to false when this function returns"
                self._battery_is_available = False  # set to true when we get a battery status message
                self._task_exception = None

            client_reader, client_writer = await asyncio.open_connection(Config.polaris_ip_address, Config.polaris_port)
            self._reader = client_reader
            self._writer = client_writer

            init_task = asyncio.create_task(self.polaris_init())
            init_task.add_done_callback(self.task_done)
            self.logger.info(f'==STARTUP== Starting Polaris Client on {Config.polaris_ip_address}:{Config.polaris_port}.')
            return True

        except Exception as e:
            self._task_errorstr = self._format_connection_error(e)
            self.logger.error(self._task_errorstr)
            self._connecting = False
            return False
    

    async def run_connection_cycle(self, max_retries):
        attempt = 0
        while (not self.lifecycle.should_shutdown()) and (attempt <= max_retries):
            try:
                attempt += 1
                success = await self.attempt_polaris_connect()
                if success:
                    await self.read_msgs()       # blocks until error or shutdown
                await asyncio.sleep(10)
        
            except Exception as e:
                self._task_errorstr = self._format_connection_error(e)
                self.logger.error(f"==STARTUP== Connection error: {self._task_errorstr}")
                await asyncio.sleep(10)

    # open connection and serve as polaris client
    async def client(self, logger: Logger):
        self.lifecycle.create_task(self._ble.runBleScanner(), name='BLEController')
        self.lifecycle.create_task(self._every_1s_watchdog_check(), name="PolarisWatchdog")
        self.lifecycle.create_task(self._every_15s_send_polaris_keepalive(), name="PolarisWatchdog")
        self.lifecycle.create_task(self.every_50ms_tick(), name="PolarisFastMove")
        if Config.log_performance_data == 2 and not Config.log_performance_data_test == 2:
            self.lifecycle.create_task(self.every_2min_drift_check(), name="PolarisDriftCheck")

        if Config.polaris_auto_retry:
            self.lifecycle.create_task(self.run_connection_cycle(float('inf')), name="PolarisConnectionCycle")
        else:
            self.logger.info("==STARTUP== Auto-restart disabled. Awaiting manual connection trigger.")

    def task_done(self, task):
        # task.exception raises an exception if the task was cancelled, so only grab it if not cancelled.
        if not task.cancelled():
            # task.exception returns None if no exception
            self._task_exception = task.exception()

    async def send_msg(self, msg):
        if self.lifecycle.should_shutdown():
            return
        parts = msg.strip('#').split('&')
        ispoll = len(parts)>1 and parts[1] in POLARIS_POLL_COMMANDS
        if (ispoll and Config.log_polaris_polling) or (not ispoll and Config.log_polaris_protocol):
            self.logger.info(f'->> Polaris: send_msg: {msg}')
        try:
            if self._writer:
                self._writer.write(msg.encode())
                await asyncio.wait_for(self._writer.drain(), timeout=2.0)
        except (ConnectionResetError, BrokenPipeError, asyncio.TimeoutError) as e:
            self._task_exception = e
            self.logger.error(f"==SEND== Failed to send message: {e}")

    async def _every_1s_watchdog_check(self):
        while True:
            try: 
                # get update on true orientation
                if self._connected:
                    await self.send_cmd_517()
                # calculate age of last 518 message
                curr_timestamp = datetime.datetime.now()
                if not self._last_518_timestamp:
                    self._last_518_timestamp = curr_timestamp
                age_of_518 = (curr_timestamp - self._last_518_timestamp).total_seconds()

                # self.logger.info(f'->> Polaris: age_of_518 is {age_of_518}s.')
                # if we dont have any updates, even after trying to restart AHRS, then reboot the connection
                if self._connected and self._aligned and age_of_518 > 5:
                    self._task_exception = WatchdogError("==ERROR==: No position update for over 5s. Rebooting Connection.")

                # if we dont have any updates for over 2s, then restart AHRS.
                if self._connected and self._aligned and age_of_518 > 2:
                    if Config.log_polaris_protocol:
                        self.logger.info(f'->> Polaris: No position update for over 2s. Restarting AHRS.')
                    await self.send_cmd_520_position_updates(True)

                await asyncio.sleep(1)

            except Exception as e:
                self._task_exception = e
                break

    async def every_2min_drift_check(self):
        while True:
            try:
                with self._lock: 
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
                    await self.send_cmd_284_query_current_mode_async()
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
        self._siderealtime =  self._observer.sidereal_time()/math.pi*12
        ra_rad, dec_rad = self._observer.radec_of(deg2rad(az), deg2rad(alt))
        ra = rad2hr(ra_rad)  
        dec = rad2deg(dec_rad)
        return ra, dec

    def radec_sync_reset(self):
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

    async def sync_to_azalt(self, a_az, a_alt):
        syncmsg = 'Multi-Point Alignment' if (Config.advanced_alignment and Config.advanced_control) else 'Single-Point Alignment'
        self.logger.info(f"->> Polaris: SYNC Observed   Az {deg2dms(a_az)} Alt {deg2dms(a_alt)} ({syncmsg})")
        await self.sync_telescope_pointing_models(a_az=a_az, a_alt=a_alt)
        return

    async def sync_to_radec(self, a_ra, a_dec):
        syncmsg = 'Multi-Point Alignment' if (Config.advanced_alignment and Config.advanced_control) else 'Single-Point Alignment'
        self.logger.info(f"->> Polaris: SYNC Observed   RA {hr2hms(a_ra)} Dec {deg2dms(a_dec)} ({syncmsg})")
        await self.sync_telescope_pointing_models(a_ra=a_ra, a_dec=a_dec)
        return

    async def sync_telescope_pointing_models(self, a_ra=None, a_dec=None, a_az=None, a_alt=None, name=None):
        if a_ra is not None and a_dec is not None:
            a_alt, a_az = self.radec2altaz(a_ra, a_dec)
        elif a_az is not None and a_alt is not None:
            a_ra, a_dec = self.altaz2radec(a_alt, a_az)
        else:
            self.logger.error("->> Polaris: SYNC Error: Must provide either RA/Dec or Alt/Az.")
            return

        if Config.advanced_alignment and Config.advanced_control:
            # Use Multi-Point Alignment and QUEST Model to determine Optimal Quaternion offset
            self.logger.info(f"->> Polaris: SYNC Observed   Az {deg2dms(a_az)} Alt {deg2dms(a_alt)}")
            self._sm.sync_az_alt(a_az, a_alt)

        else:
            # Use Single-Point Alignment and Alt/Az Sync Pointing model, send through to Polaris
            asyncio.create_task(self.send_cmd_star_alignment(a_az, a_alt))

        self._rightascension = a_ra 
        self._declination = a_dec
        self._targetrightascension = a_ra
        self._targetdeclination = a_dec
        self._altitude = a_alt
        self._azimuth = a_az
        self._pid.alpha_sp[0] = a_az
        self._pid.alpha_sp[1] = a_alt
        self._pid.delta_sp[0] = a_ra * 15
        self._pid.delta_sp[1] = a_dec
        corrected_position_angle, _ = self._sm.roll2pa(a_az, a_alt, self._roll) # to preserve roll
        self._pid.delta_sp[2] = corrected_position_angle
        self.logger.info(f"->> Polaris: DeltaSP    RA {hr2hms(self._pid.delta_sp[0])} Dec {deg2dms(self._pid.delta_sp[1])} PA {deg2dms(self._pid.delta_sp[2])}")
        self.logger.info(f"->> Polaris: DeltaOfft  RA {hr2hms(self._pid.delta_offst[0])} Dec {deg2dms(self._pid.delta_offst[1])} PA {deg2dms(self._pid.delta_offst[2])}")

        return

    async def skip_compass_alignment(self, compass):
            await self.send_cmd_compass_alignment(compass)
            await self.send_cmd_284_query_current_mode()


    async def skip_star_alignment(self, azimuth, altitude):
            self._aligning = True
            await self.send_cmd_star_alignment(azimuth, altitude)
            await self.send_cmd_284_query_current_mode()
            self._aligning = False

    async def read_msgs(self):
        buffer = ""
        try:
            while not self.lifecycle.should_shutdown():
                # Raise any subtask exceptions immediately
                if self._task_exception:
                    raise self._task_exception

                # Read from Polaris
                if self._reader:
                    try:
                        data = await asyncio.wait_for(self._reader.read(1024), timeout=2.0)
                    except asyncio.TimeoutError:
                        continue  # No data, keep looping
                    except (ConnectionResetError, BrokenPipeError) as e:
                        self.logger.error(f"==DISCONNECT== Polaris socket error: {e}")
                        self._connecting = False
                        break
                    if not data:
                        self.logger.warn("==DISCONNECT== Polaris socket closed.")
                        self._connecting = False
                        break

                    buffer += data.decode()

                # Parse all messages in the buffer
                while True:
                    cmd, args, new_buffer = self.parse_msg(buffer)
                    if cmd:
                        buffer = new_buffer
                        ispoll = cmd in POLARIS_POLL_COMMANDS
                        if (ispoll and Config.log_polaris_polling) or (not ispoll and Config.log_polaris_protocol):
                            self.logger.info(f'<<- Polaris: recv_msg: {cmd}@{args}#')
                        self.polaris_parse_cmd(cmd, args)
                    else:
                        break  # No complete message yet — wait for more data

                # Avoid tight loop
                await asyncio.sleep(0.05)

        except asyncio.CancelledError:
            self.logger.info("==CANCELLED== PolarisReadMsgs cancelled.")
            self._connecting = False
            raise

        except Exception as e:
            self._task_exception = e
            self.logger.error(f"==ERROR== read_msgs failed: {e}")
            self._connecting = False

    # Parse a buffer returning a matched (cmd, args, remainingBuffer) or when no match (None, None, remainingBuffer)
    def parse_msg(self, buffer):
        m = self._polaris_msg_re.search(buffer)
        if m:
            start, end = m.span()
            cmd = m.group(1)
            args = m.group(2)
            remaining = buffer[end:]
            if start > 0 and Config.log_polaris_protocol:
                self.logger.warn(f"<<- Polaris: Discarding junk protocol: {bytes2hexascii(buffer[:start].encode())}")
            return (cmd, args, remaining)
        else:
            # No complete message yet — wait for more data
            return (None, None, buffer)

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
            with self._lock:
                self._polaris_mode = int(arg_dict['mode'])
                if self._polaris_mode == 8:
                    isAligned = not arg_dict.get('track') == '3'
                    self._tracking_in_benro = arg_dict.get('track') == '1'
                    self._aligned = isAligned
                    self._compassed = isAligned
                if not (Config.advanced_tracking and Config.advanced_control):        # only update tracking if Benro in control
                    self._tracking = self._tracking_in_benro
            if Config.log_polaris_polling:
                self.logger.info(f"<<- Polaris: MODE status changed: {cmd} {arg_dict}")
            if cmd in self._response_queues:
                self._response_queues[cmd].put_nowait(arg_dict)

        # return result of set Mode {} 
        elif cmd == "285":
            arg_dict = self.polaris_parse_args(args)
            if arg_dict.get('ret') == '0':
                with self._lock:
                    self._polaris_mode = int(arg_dict['mode'])

        # return result of Query Orientation request {} 
        elif cmd == "517":
            arg_dict = self.polaris_parse_args(args)
            # Orientation of each axis motor rotational position in radians
            # Typical Park Position yaw=-0.000280, pitch=0.000267, roll=0.000375
            # yaw   = axis1 E rotation in radians (-2pi=-360, -pi=-180, 0=Park, pi=180;, 2pi=360, 3pi=540, etc.)
            # pitch = axis2 down rotation in radians (-0.6144=highest/83d00'37", 0=Park/47d46'06", 0.834020=0d, 0.914842=lowest/-04d38'04")
            # roll  = axis3 cw rotation in radians (-2pi=-360, -pi=-180, 0=Park, pi=180;, 2pi=360, 3pi=540', etc.)
            p_yaw = rad2deg(float(arg_dict['yaw']))         # from Polaris direct
            p_pitch = -rad2deg(float(arg_dict['pitch']))    # from Polaris direct, note sign switch to align with Alt direction
            p_roll = rad2deg(float(arg_dict['roll']))       # from Polaris direct
            with self._lock:
                self._zeta_meas = [p_yaw, p_pitch, p_roll]
            if Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: GET ORIENTATION results: {cmd} {arg_dict}")

        # return result of POSITION update from AHRS {} 
        elif cmd == "518":
            dt_now = datetime.datetime.now()
    
            # extract the quaternion and derive its angles and velocities
            arg_dict = self.polaris_parse_args(args, name_postfix=True)
            q1 = Quaternion(arg_dict['w1'], arg_dict['x1'], arg_dict['y1'], arg_dict['z1'])
            p_az = float(arg_dict['compass'])   # from Polaris direct
            p_alt = -float(arg_dict['alt'])     # from Polaris direct
            q_t1, q_t2, q_t3, q_az, q_alt, q_roll = quaternion_to_angles(q1, azhint=p_az)
            q_ra, q_dec = self.altaz2radec(q_alt, q_az)
            theta_meas = np.array([q_t1, q_t2, q_t3])
            self._history.append([dt_now, q_t1, q_t2, q_t3])          # deque collection, so it automatically throws away stuff older than 6 samples ago
            omega_meas = calculate_angular_velocity(self._history)
            omega_ref = np.array([controller.rate_dps for controller in self._motors.values()])

            # Store all the polaris values
            with self._lock:
                self._last_518_timestamp = dt_now
                self._q1 = q1
                self._theta_meas = theta_meas
                self._omega_meas = omega_meas
                self._p_azimuth = float(q_az)
                self._p_altitude = float(q_alt)
                self._p_roll = float(q_roll)
                self._p_rightascension = float(q_ra) 
                self._p_declination = float(q_dec)

            # Process through the Kalman Filter to determine Polaris theta_state (uncorrected for alignment)
            self._kf.predict(omega_ref)
            self._kf.observe(theta_meas, omega_meas, omega_ref)
            theta_state, _ = self._kf.get_state()
            q1_state = motors_to_quaternion(*theta_state)

            # Flag when variance from quaternion q_az and p_az
            if not is_angle_same(q_az, p_az):
                self.logger.warn(f"Kinematics variance p_az {p_az:.5f} q_az {q_az:.5f} diff {p_az - q_az:.5f} ")              
            if not is_angle_same(q_alt, p_alt):
                self.logger.warn(f"Kinematics variance p_alt {p_alt:.5f} q_alt {q_alt:.5f} diff {p_alt - q_alt:.5f}") 

            # Use direct measurements if no KF
            if not (Config.advanced_kf and Config.advanced_control):
                q1_state, theta_state = q1, theta_meas

            # update all the ASCOM values and the PID loop
            delta_state, alpha_state, theta_state = self.update_ascom_from_new_q1_adj(q1_state, azhint=p_az)
            self._pid.measure(delta_state, alpha_state, theta_state, self._zeta_meas)


        # return result of GOTO request {'ret': 'X', 'track': '1'}  X=1 (starting slew), X=2 (stopping slew)
        elif cmd == "519":
            arg_dict = self.polaris_parse_args(args)
            if cmd in self._response_queues:
                self._response_queues[cmd].put_nowait(arg_dict)

        # return result of UNKNOWN command SP_SendMsgToApp success;type[2],code[525],val[Tempa509ca361d0000265a ;]
        elif cmd == "525":
            if Config.log_polaris_polling:
                self.logger.info(f"<<- Polaris: 525 status changed: {cmd} {args}")

        # return result of SET COMPASS
        elif cmd == "527":
            arg_dict = self.polaris_parse_args(args)
            self._compassed = arg_dict.get('ret') == '0'
            if Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: 527 Set Compass: {cmd} {arg_dict}")

        # return result of TRACK change request {'ret': 'X'} where X=0 (NoTracking), X=1 (Tracking)
        elif cmd == "531":
            arg_dict = self.polaris_parse_args(args)
            with self._lock:
                self._tracking_in_benro = arg_dict.get('ret') == '1'
                if not (Config.advanced_tracking and Config.advanced_control):        # only update tracking if Benro in control
                    self._tracking = self._tracking_in_benro
            if Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: TRACK status changed: {cmd} {arg_dict}")
            if cmd in self._response_queues:
                self._response_queues[cmd].put_nowait(arg_dict)

        # return result of FILE request {'type':1; 'class':0; 'path':'/app/sd/normal/SP_0052.jpg'; 'size':'916156'; 'cTime':'2023-10-24 22:33:12'; 'duration':'0'} 
        elif cmd == "771":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: FILE status changed: {cmd} {arg_dict}")

        # return result of STORAGE request {'status': '1', 'totalspace': '30420', 'freespace': '30163', 'usespace': '256'} 
        elif cmd == "775":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: STORAGE status changed: {cmd} {arg_dict}")

        # return result of BATTTERY request {'capacity': 'X', 'charge': 'Y'}  X=batttery%, Y=1 (charging), Y=0 (draining)
        elif cmd == "778":
            arg_dict = self.polaris_parse_args(args)
            with self._lock:
                self._battery_is_available = True
                self._battery_is_charging = (arg_dict['charge'] == '1')
                self._battery_level = int(arg_dict['capacity'])
            self.logger.info(f"<<- Polaris: BATTERY status changed: {cmd} {arg_dict}")

        # return result of VERSION request {'hw':'1.3.1.4'; 'sw': '6.0.0.40'; 'exAxis':'1.0.2.11'; 'sv':'1'} 
        elif cmd == "780":
            arg_dict = self.polaris_parse_args(args)
            with self._lock:
                self._polaris_sw_ver = arg_dict.get('sw')
                self._polaris_hw_ver = arg_dict.get('hw')
            if Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: VERSION status changed: {cmd} {arg_dict}")

        # return result of SECURITY request {'step': '1', 'password': 'YmVucm8=', 'securityQ': '2', 'securityA': 'QnJhaW4='}
        elif cmd == "790":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: SECURITY status changed: {cmd} {arg_dict}")

        # return result of WIFI request {'band': '1'}
        elif cmd == "802":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: WIFI status changed: {cmd} {arg_dict}")

        # return result of Connection request result {'ret': '0'}
        elif cmd == "808":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: Connection request result: {cmd} {arg_dict}")

        # return result of Position Updaten request result {'ret': '1'}
        elif cmd == "520":
            arg_dict = self.polaris_parse_args(args)
            if Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: Position Update request result: {cmd} {arg_dict}")

        # return result of unrecognised msg
        else:
            if Config.log_polaris_protocol:
                self.logger.info(f"<<- Polaris: response to command received: {cmd} {args}")



    def update_ascom_from_new_q1_adj(self, q1_state, azhint):
        # default to the ASCOM az,alt,roll values based on a q1 state
        a_t1, a_t2, a_t3, a_az, a_alt, a_roll = quaternion_to_angles(q1_state, azhint=azhint)

        # Correct the ASCOM az,alt,roll values with the Multi-Point QUEST optimal adj and re-grab
        if Config.advanced_alignment and Config.advanced_control:        
            _, _, _, a_az, a_alt, a_roll = quaternion_to_angles(self._sm.q1_adj * q1_state, azhint=azhint)

        # Correct the ASCOM roll value with the Rotator adj
        if Config.advanced_rotator and Config.advanced_control:         
            a_roll = self._sm.roll_polaris2ascom(a_roll)

        a_ra, a_dec = self.altaz2radec(a_alt, a_az)
        position_ang, parallactic_ang = self._sm.roll2pa(a_az, a_alt, a_roll)
        alpha_state = np.array([a_az, a_alt, a_roll], dtype=float)
        theta_state = np.array([a_t1, a_t2, a_t3], dtype=float)          # always unadjusted
        delta_state = np.array([a_ra*15, a_dec, -position_ang], dtype=float)         
    
        # Store all the new ascom values
        with self._lock:
            self._q1s = q1_state
            self._theta_state = theta_state             # based on polaris q1 (unadjusted)
            self._altitude = float(a_alt)
            self._azimuth = float(a_az)
            self._roll = float(a_roll)
            self._rotation = float(a_t3)
            self._rightascension = float(a_ra) 
            self._declination = float(a_dec)
            self._position_angle = float(position_ang)
            self._parallactic_angle = float(parallactic_ang)

        return delta_state, alpha_state, theta_state

    def aim_altaz_log_result(self):
        with self._lock:
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
        time = self.get_performance_data_time()
        self.logger.info(f"->> Polaris: GOTO AimOffset (Az {deg2dms(adj_az)} Alt {deg2dms(adj_alt)}) | Error Az {err_az*3600:.3f} Alt {err_alt*3600:.3f}")
        # if we want to log Aim data
        if Config.log_performance_data == 1:
            self.logger.info(f",DATA1,{time:.3f},{a_az:.7f},{a_alt:.7f},{adj_az:.7f},{adj_alt:.7f},{err_az*3600:.3f},{err_alt*3600:.3f}")

    def aim_altaz_log_and_correct(self, alt: float, az:float):
        # log the original aiming co-ordinates and grab the last error ajustments
        with self._lock:
            self._aim_altitude = alt
            self._aim_azimuth = az
            adj_alt = self._adj_altitude
            adj_az = self._adj_azimuth

        # ajust the aiming altaz and clap az being sent to the Polaris -180° < polaris_az < 180°
        calt = alt + adj_alt if Config.aiming_adjustment_enabled else alt
        caz = az + adj_az if Config.aiming_adjustment_enabled else az
        caz = 360 - caz if caz>180 else -caz
        return (calt, caz)

    async def send_cmd_change_tracking_state(self, tracking: bool):
        cmd = '531'
        state = 1 if tracking else 0
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: TRACK request change to {state}")
        empty_queue(self._response_queues[cmd])
        await self.send_msg(f"1&{cmd}&3&state:{state};speed:0;#")
        await self._response_queues[cmd].get() 

    # Abort Slew
    # eg state:0;yaw:0.0;pitch:0.0;lat:-33.655422;track:0;speed:0;lng:151.12244;
    async def send_cmd_goto_abort(self):
        with self._lock:
            self._slewing = False
            self._gotoing = False
        # log the command
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: GOTO ABORT")
        arg_dict = {'ret': '-1', 'track': '-1'}
        cmd = '519'
        msg = f"1&{cmd}&3&state:0;yaw:0.0;pitch:0.0;lat:{self._sitelatitude:.5f};track:0;speed:0;lng:{self._sitelongitude:.5f};#"
        await self.send_msg(msg)
        self._response_queues[cmd].put_nowait(arg_dict)
        self._response_queues[cmd].put_nowait(arg_dict)

    # Assumes polaris altaz
    async def send_cmd_goto_altaz(self, alt, az, istracking = True):
        with self._lock:
            currently_slewing = self._slewing
            currently_gotoing = self._gotoing
            currently_tracking = self._tracking

        # if we are currently slewing or gotoing, dont try again
        if currently_slewing or currently_gotoing:
            self.logger.info(f"->> Polaris: GOTO CANNOT EXECUTE due to current slew {currently_slewing} or goto {currently_gotoing}")
            return

        # Mark that we are gotoing and slewing
        with self._lock:
            self._slewing = True
            self._gotoing = True

        # log the command
        if Config.log_polaris_protocol:
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
        if Config.log_polaris_protocol:
            self.logger.info(f"<<- Polaris: GOTO starting slew: {cmd} {ret_dict}")
            
        # wait for 2nd response of slew stopped
        ret_dict = await self._response_queues[cmd].get()
        if Config.log_polaris_protocol:
            self.logger.info(f"<<- Polaris: GOTO stopping slew: {cmd} {ret_dict}")

        # wait for sidereal tracking to settle
        await asyncio.sleep(Config.tracking_settle_time)

        # mark the slew as complete      
        with self._lock:
            self._slewing = False
            self._gotoing = False
        if Config.log_polaris_protocol:
            self.logger.info(f"<<- Polaris: GOTO slew complete")

        # log the result of the goto if it was NOT aborted and is a tracking GOTO
        if (not (ret_dict["ret"] == '-1')) and istracking:
            self.aim_altaz_log_result()

        return ret_dict

    async def send_cmd_reset_axis(self, axis:int):
        if axis==0 or axis==1 or axis==2:
            polaris_axis = axis + 1
            await self.send_msg(f"1&523&3&axis:{polaris_axis};#")

    async def send_cmd_compass_alignment(self, angle:float = None):
        # use angle provided or assume synced ASCOM azimuth
        a_az = angle if angle else self._azimuth
        compass = (a_az - 180.0) % 360
        lat = self._sitelatitude
        lon = self._sitelongitude
        self._adj_sync_azimuth = 0
        await self.send_msg(f"1&527&3&compass:{compass};lat:{lat};lng:{lon};#")

    async def send_cmd_star_alignment(self, a_az:float, a_alt:float):
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
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: PARK all 3 axis")
        await self.send_cmd_reset_axis(0)
        await self.send_cmd_reset_axis(1)
        await self.send_cmd_reset_axis(2)

    async def send_cmd_824(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 824 request")
        msg = f"1&824&3&-100#"
        await self.send_msg(msg)

    async def send_cmd_808(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 808 Connection request")
        msg = f"1&808&2&type:0;#"
        await self.send_msg(msg)

    async def send_cmd_802(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 802 Band request")
        msg = f"1&802&3&-100#"
        await self.send_msg(msg)

    async def send_cmd_799(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 799 request")
        msg = f"1&799&2&-100#"
        await self.send_msg(msg)

    async def send_cmd_790(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 790 Pswd and Challenge request")
        msg = f"1&790&2&step:1#"
        await self.send_msg(msg)

    async def send_cmd_782(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 782 SET DATETIME request")
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        offset_seconds = int(now.utcoffset().total_seconds())
        msg = f"1&782&2&date:{date_str};time:{time_str};zone:{offset_seconds:+d}#"
        await self.send_msg(msg)

    async def send_cmd_780(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 780 QUERY FIRMWARE request")
        msg = f"1&780&2&-100#"
        await self.send_msg(msg)

    async def send_cmd_778(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 778 Battery status request")
        msg = f"1&778&2&-1#"
        await self.send_msg(msg)

    async def send_cmd_775(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 775 Query SD Card request")
        msg = f"1&775&2&-100#"
        await self.send_msg(msg)

    async def send_cmd_547(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 547 request")
        msg = f"1&547&3&-100#"
        await self.send_msg(msg)

    async def send_cmd_524(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 524 request")
        msg = f"1&524&3&-100#"
        await self.send_msg(msg)

    async def send_cmd_520_position_updates(self, state:bool=True):
        state = "1" if state else "0"
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 520 Position Updates request")
        msg = f"1&520&2&state:{state};#"
        await self.send_msg(msg)

    async def send_cmd_517(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 517 Get Orientation request")
        msg = f"1&517&3&-1#"
        await self.send_msg(msg)

    async def send_cmd_305(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 305 request")
        msg = f"1&305&2&step:2;#"
        await self.send_msg(msg)

    async def send_cmd_303(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 303 request")
        msg = f"1&303&2&-1#"
        await self.send_msg(msg)

    async def send_cmd_300(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 300 Query HDMI request")
        msg = f"1&300&2&-100#"
        await self.send_msg(msg)

    async def send_cmd_298(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 298 Query Extime request")
        msg = f"1&298&2&-100#"
        await self.send_msg(msg)

    async def send_cmd_296_query_mode(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 296 Query Mode request")
        msg = f"1&296&2&-100#"
        await self.send_msg(msg)
        
    async def send_cmd_285_set_mode(self, mode):
        if mode<1 or mode>10: 
            self.logger.info(f"Invalid 285 Polaris Set Mode request {mode}")
            return
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 285 Set Mode request {mode}")
        msg = f"1&285&2&mode:{mode}#"
        await self.send_msg(msg)

    async def send_cmd_284_query_current_mode(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: MODE query status info request")
        cmd = '284'
        msg = f"1&{cmd}&2&-1#"
        empty_queue(self._response_queues[cmd])
        await self.send_msg(msg)
        ret_dict = await self._response_queues[cmd].get()
        return ret_dict

    async def send_cmd_284_query_current_mode_async(self):
        if Config.log_polaris_polling:
            self.logger.info(f"->> Polaris: 284 Query Mode request")
        msg = f"1&284&2&-1#"
        await self.send_msg(msg)

    async def send_cmd_272(self):
        if Config.log_polaris_protocol:
            self.logger.info(f"->> Polaris: 272 request")
        msg = f"1&272&2&step:10#"
        await self.send_msg(msg)


    async def polaris_init(self):
        self.logger.info("Polaris communication init...")
        await self.send_cmd_790()
        await self.send_cmd_799()
        await self.send_cmd_296_query_mode()
        await self.send_cmd_300()
        await self.send_cmd_298()
        await asyncio.sleep(0.5)
        await self.send_cmd_520_position_updates(True)
        await self.send_cmd_524()
        await self.send_cmd_782()
        await self.send_cmd_778()
        await self.send_cmd_775()
        ret_dict = await self.send_cmd_284_query_current_mode()
        await self.send_cmd_802()
        await self.send_cmd_824()
        # 286
        await self.send_cmd_780()
        await self.send_cmd_305()
        await self.send_cmd_272()
        await self.send_cmd_547()
        await self.send_cmd_808()   # Connection Context
        await self.send_cmd_520_position_updates(True)
        # 523 Reset axes
        # 543
        # 285 Mode 8
        # 284
        # 520
        # 527 Compass
        # 520
        # 284
        # 519 type:3;code:519;val:state:1;yaw:-166.577;pitch:61.513;lat:-33.655254;track:0;speed:0;lng:151.12231;
        # 530
        self._connecting = False

        # if  'mode' in ret_dict and int(ret_dict['mode']) == 8:
        #     if 'track' in ret_dict and int(ret_dict['track']) == 3:
        #         # Polaris is in astro mode but alignment not complete
        #         raise AstroAlignmentError()
        # else:
        #     # Polaris is not in astro mode
        #     raise AstroModeError()

        # Completed initialisation
        with self._lock:
            self._connected = True
            self._task_errorstr = ''
        s_lat = self._sitelatitude
        s_lon = self._sitelongitude
        self.logger.info("Polaris communication init... done")
        self.logger.info(f'Site lat = {s_lat} ({deg2dms(s_lat)}) | lon = {s_lon} ({deg2dms(s_lon)}).')
        self.logger.warn(f'Change site_latitude and site_longitude in Alpaca Pilot App or use Nina/StellariumPLUS to sync.')
        # if we want to run Aim test or Drift test over a set of targets in the sky
        if Config.log_performance_data_test == 1 or Config.log_performance_data_test == 2:
            asyncio.create_task(self.goto_tracking_test())
        if Config.log_performance_data_test == 5:
            asyncio.create_task(self.rotator_test())


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


    async def moveaxis_speed_test(self, axis, rates):
        self.lifecycle.start()
        motor = self._motors[axis]
        for rate in rates:
            if self.lifecycle.should_stop():
                break
            direction = +1
            # check axis 1 bounds and reverse direction if necc 
            if axis==1 and self._theta_meas.any():
                if self._theta_meas[1] > 60:
                    await motor.set_motor_speed(0, "RAW")
                    await asyncio.sleep(3)
                    direction = -1
                if self._theta_meas[1] < 20:
                    await motor.set_motor_speed(0, "RAW")
                    await asyncio.sleep(3)
                    direction = +1
            # send the move request
            await motor.set_motor_speed(rate * direction, "RAW")
            result, raw, stdev, status = await self.moveaxis_speed_measurement(axis, rate)
            self._cm.addTestResult(axis, rate, result, stdev, status)
        # ensure we stop all movement
        await motor.set_motor_speed(0, "RAW")
        await asyncio.sleep(2)
        await self.send_cmd_reset_axis(axis)
        self.lifecycle.reset()


    async def moveaxis_speed_measurement(self, axis, rate, required_stable_samples = 5, initial_interval = 3.0, max_interval = 15, sampling_interval = 0.25):
        start_time = time.monotonic()
        stable_tolerance = 0.05 if rate > 5 else 0.002
        await asyncio.sleep(initial_interval)
        rate_raw = self._motors[axis].rate_raw    # what the controller thinks the raw rate is
        rate_dps = self._motors[axis].rate_dps    # what the controller thinks the dps rate is
        status = "COMPLETED"

        omega_samples = []     # deg/sec
        while time.monotonic() - start_time < max_interval:
            await asyncio.sleep(sampling_interval)
            if self.lifecycle.should_stop():
                return 0,0,0,"STOPPED"
            if self._omega_meas is None:
                return 0,0,0,"NO DATA"
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
            status = "HIGH STDEV"
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
        with self._lock:
            res = self._connected
        return res

    def connectionquery(self, client: str):
        with self._lock:
            # if no record of client, assume it was connected so that it can continue working
            if not client in self._connections:
                self._connections[client] = True
            res = self._connections[client]
        return res
                          
    def connectionrequest(self, client: str, connect: bool):
        with self._lock:
            self._connections[client] = connect
            numclients = sum(v for v in self._connections.values() if v)
        if Config.log_polaris_protocol:
            self.logger.info(f'[connection request] Client {client} Connected: {connect} Total Connected Clients: {numclients}')

        # check is any exceptions with polaris.client() and polaris_init() last run
        if  self._task_errorstr:
            raise Exception(self._task_errorstr)

    def getStatus(self) -> dict:
        with self._lock:
            res = {
                'polarismode': self._polaris_mode,
                'battery_is_available': self._battery_is_available,
                'battery_is_charging': self._battery_is_charging,
                'battery_level': self._battery_level,
                'compassed': self._compassed,
                'aligned': self._aligned,
                'aligning': self._aligning,
                'aligned_count': self._sm.aligned_count,
                'tilt_adj_az': self._sm.tilt_adj_az,
                'tilt_adj_mag': self._sm.tilt_adj_mag,
                'az_adj': self._sm.az_adj,
                'roll_adj': self._sm.roll_adj,
                'connected': self._connected,
                'connecting': self._connecting,
                'connectionmsg': self._task_errorstr,
                'tracking': self._tracking,
                'trackingrate': self._trackingrate,
                'athome': self._athome,
                'atpark': self._atpark,
                'slewing': self._slewing,
                'gotoing': self._gotoing,
                'rotating': self._rotating,
                'ispulseguiding': self._ispulseguiding,
                'paltitude': self._p_altitude,
                'pazimuth': self._p_azimuth,
                'proll': self._p_roll,
                'altitude': self._altitude,
                'azimuth': self._azimuth,
                'roll': self._roll,
                'rotation': self._rotation,
                'declination': self._declination,
                'rightascension': self._rightascension,
                'parallacticangle': self._parallactic_angle,
                'positionangle': self._position_angle,
                'pidmode': self._pid.mode,                
                'q1': str(self._q1),
                'q1s': str(self._q1s),
                'zetameas': [0,0,0] if self._zeta_meas is None else self._zeta_meas,
                'lotameas': [0,0,0,0,0] if self._theta_meas is None else [self._p_azimuth, self._p_altitude, self._p_roll, self._p_rightascension, self._p_declination],
                'thetameas': [0,0,0] if self._theta_meas is None else self._theta_meas.tolist(),
                'thetastate': [0,0,0] if self._theta_state is None else self._theta_state.tolist(),
                'deltaref': self._pid.delta_ref.tolist(),
                'alpharef': self._pid.alpha_ref.tolist(),
                'omegaref': self._pid.omega_ref.tolist(),
                'omegamin': self._pid.omega_min.tolist(),
                'omegamax': self._pid.omega_max.tolist(),
                'motorref': [motor.rate_dps for motor in self._motors.values()],
                'siderealtime': self._siderealtime,
                'lifecycleevent': self.lifecycle._event.name,
                'bledevices' : [info["name"] for info in self._ble.devices.values()],
                'bleselected' : self._ble.selectedDevice,
                'bleisenablingwifi': self._ble.isEnablingWifi,
                'bleiswifienabled': self._ble.isWifiEnabled,
                'polarisswver': self._polaris_sw_ver,
                'polarishwver': self._polaris_hw_ver,
            }
        return res

    @property
    def tracking(self) -> bool:
        with self._lock:
            res = self._tracking
        return res
    @tracking.setter
    def tracking (self, tracking: int):
        with self._lock:
            self._tracking = tracking

    @property
    def sideofpier(self) -> int:
        with self._lock:
            res =  self._sideofpier
        return res
    @sideofpier.setter
    def sideofpier (self, sideofpier: int):
        with self._lock:
            self._sideofpier = sideofpier

    @property
    def athome(self) -> bool:
        with self._lock:
            res =  self._athome
        return res

    @property
    def atpark(self) -> bool:
        with self._lock:
            res =  self._atpark
        return res

    @property
    def slewing(self) -> bool:
        with self._lock:
            res =  self._slewing
        return res

    @property
    def gotoing(self) -> bool:
        with self._lock:
            res =  self._gotoing
        return res

    @property
    def rotating(self) -> bool:
        with self._lock:
            res =  self._rotating
        return res

    @property
    def ispulseguiding(self) -> bool:
        with self._lock:
            res =  self._ispulseguiding
        return res
    #
    # Telescope device variables
    #
    @property
    def altitude(self) -> float:
        with self._lock:
            res =  self._altitude
        return res

    @property
    def azimuth(self) -> float:
        with self._lock:
            res =  self._azimuth
        return res

    @property
    def roll(self) -> float:
        with self._lock:
            res =  self._roll
        return res

    @property
    def rotation(self) -> float:
        with self._lock:
            res =  self._rotation
        return res

    @property
    def positionangle(self) -> float:
        with self._lock:
            res =  self._position_angle
        return res

    @property
    def declination(self) -> float:
        with self._lock:
            res =  self._declination
        return res

    @property
    def rightascension(self) -> float:
        with self._lock:
            res =  self._rightascension
        return res

    @property
    def siderealtime(self) -> float:
        with self._lock:
            res =  self._siderealtime
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
        with self._lock:
            res =  self._trackingrate
        return res
    @trackingrate.setter
    def trackingrate (self, trackingrate: int):
        with self._lock:
            self._trackingrate = trackingrate

    @property
    def trackingrates(self):
        with self._lock:
            res =  self._trackingrates
        return res

    @property
    def declinationrate(self) -> float:
        with self._lock:
            res =  self._declinationrate
        return res
    @declinationrate.setter
    def declinationrate (self, declinationrate: float):
        with self._lock:
            self._declinationrate = declinationrate

    @property
    def rightascensionrate(self) -> float:
        with self._lock:
            res =  self._rightascensionrate
        return res
    @rightascensionrate.setter
    def rightascensionrate (self, rightascensionrate: float):
        with self._lock:
            self._rightascensionrate = rightascensionrate

    @property
    def guideratedeclination(self) -> float:
        with self._lock:
            res =  self._guideratedeclination
        return res
    @guideratedeclination.setter
    def guideratedeclination (self, guideratedeclination: float):
        with self._lock:
            self._guideratedeclination = guideratedeclination

    @property
    def guideraterightascension(self) -> float:
        with self._lock:
            res =  self._guideraterightascension
        return res
    @guideraterightascension.setter
    def guideraterightascension (self, guideraterightascension: float):
        with self._lock:
            self._guideraterightascension = guideraterightascension
    #
    # Rotator device settings
    #
    @property
    def rotator_reverse(self) -> int:
        with self._lock:
            res =  self._rotator_reverse
        return res
    @rotator_reverse.setter
    def rotator_reverse(self, state: bool):
        with self._lock:
            self._rotator_reverse = state
    #
    # Telescope device settings
    #
    @property
    def alignmentmode(self) -> int:
        with self._lock:
            res =  self._alignmentmode
        return res

    @property
    def aperturearea(self) -> float:
        with self._lock:
            res =  self._aperturearea
        return res

    @property
    def aperturediameter(self) -> float:
        with self._lock:
            res =  self._aperturediameter
        return res

    @property
    def equatorialsystem(self) -> float:
        with self._lock:
            res =  self._equatorialsystem
        return res

    @property
    def focallength(self) -> float:
        with self._lock:
            res = self._focallength
        return res

    @property
    def sitepressure(self) -> float:
        with self._lock:
            res = self._sitepressure
        return res
    @sitepressure.setter
    def sitepressure (self, sitepressure: float):
        with self._lock:
            self._sitepressure = sitepressure
            self._observer.pressure = sitepressure

    @property
    def siteelevation(self) -> float:
        with self._lock:
            res = self._siteelevation
        return res
    @siteelevation.setter
    def siteelevation (self, siteelevation: float):
        with self._lock:
            self._siteelevation = siteelevation
            self._observer.elevation = siteelevation

    @property
    def sitelatitude(self) -> float:
        with self._lock:
            res = self._sitelatitude
        return res
    @sitelatitude.setter
    def sitelatitude (self, sitelatitude: float):
        with self._lock:
            self._sitelatitude = sitelatitude
            self._observer.lat = deg2rad(sitelatitude) 

    @property
    def sitelongitude(self) -> float:
        with self._lock:
            res =  self._sitelongitude
        return res
    @sitelongitude.setter
    def sitelongitude (self, sitelongitude: float):
        with self._lock:
            self._sitelongitude = sitelongitude
            self._observer.long = deg2rad(sitelongitude) 
    
    @property
    def slewsettletime(self) -> int:
        with self._lock:
            res =  self._slewsettletime
        return res
    @slewsettletime.setter
    def slewsettletime (self, slewsettletime: int):
        with self._lock:
            self._slewsettletime = slewsettletime

    @property
    def supportedactions(self) -> float:
        with self._lock:
            res =  self._supportedactions
        return res

    @property
    def targetdeclination(self) -> float:
        with self._lock:
            res =  self._targetdeclination
        return res
    @targetdeclination.setter
    def targetdeclination (self, targetdeclination: float):
        with self._lock:
            self._targetdeclination = targetdeclination

    @property
    def targetrightascension(self) -> float:
        with self._lock:
            res =  self._targetrightascension
        return res
    @targetrightascension.setter
    def targetrightascension (self, targetrightascension: float):
        with self._lock:
            self._targetrightascension = targetrightascension

    @property
    def targetpositionangle(self) -> float:
        with self._lock:
            res =  self._targetpositionangle
        return res
    @targetpositionangle.setter
    def targetpositionangle (self, targetpositionangle: float):
        with self._lock:
            self._targetpositionangle = targetpositionangle
    #
    # Telescope capability constants
    #
    @property
    def canfindhome(self) -> bool:
        with self._lock:
            res =  self._canfindhome
        return res

    @property
    def canpark(self) -> bool:
        with self._lock:
            res =  self._canpark
        return res

    @property
    def canpulseguide(self) -> bool:
        with self._lock:
            res =  self._canpulseguide
        return res

    @property
    def cansetdeclinationrate(self) -> bool:
        with self._lock:
            res =  self._cansetdeclinationrate
        return res

    @property
    def cansetguiderates(self) -> bool:
        with self._lock:
            res =  self._cansetguiderates
        return res

    @property
    def cansetpark(self) -> bool:
        with self._lock:
            res =  self._cansetpark
        return res

    @property
    def cansetpierside(self) -> bool:
        with self._lock:
            res =  self._cansetpierside
        return res

    @property
    def cansetrightascensionrate(self) -> bool:
        with self._lock:
            res =  self._cansetrightascensionrate
        return res

    @property
    def cansettracking(self) -> bool:
        with self._lock:
            res =  self._cansettracking
        return res

    @property
    def canslew(self) -> bool:
        with self._lock:
            res =  self._canslew
        return res

    @property
    def canslewasync(self) -> bool:
        with self._lock:
            res =  self._canslewasync
        return res

    @property
    def canslewaltaz(self) -> bool:
        with self._lock:
            res =  self._canslewaltaz
        return res

    @property
    def canslewaltazasync(self) -> bool:
        with self._lock:
            res =  self._canslewaltazasync
        return res

    @property
    def cansync(self) -> bool:
        with self._lock:
            res =  self._cansync
        return res

    @property
    def cansyncaltaz(self) -> bool:
        with self._lock:
            res =  self._cansyncaltaz
        return res

    @property
    def canunpark(self) -> bool:
        with self._lock:
            res =  self._canunpark
        return res

    @property
    def doesrefraction(self) -> bool:
        with self._lock:
            res =  self._doesrefraction
        return res
    @doesrefraction.setter
    def doesrefraction (self, doesrefraction: float):
        with self._lock:
            self._doesrefraction = doesrefraction
            self._observer.pressure = Config.site_pressure if doesrefraction else 0
    #
    # Telescope method constants
    #
    @property
    def axisrates(self) -> bool:
        with self._lock:
            res =  self._axisrates
        return res

    @property
    def canmoveaxis(self) -> bool:
        with self._lock:
            res =  self._canmoveaxis
        return res

    
    


    ####################################################################
    # Methods
    ####################################################################

    def markGotoAsUnderway(self):
        with self._lock:
            self._slewing = True
            self._gotoing = True
            self._goto_complete_event = asyncio.Event()

    def markGotoAsComplete(self):
        with self._lock:
            self._slewing = False
            self._gotoing = False
            if self._goto_complete_event:
                self._goto_complete_event.set() 

    def markRotateAsUnderway(self):
        with self._lock:
            self._rotating = True
            self._rotate_complete_event = asyncio.Event()

    def markRotateAsComplete(self):
        with self._lock:
            self._rotating = False
            if self._rotate_complete_event:
                self._rotate_complete_event.set() 

    def markSlewAsUnderway(self):
        with self._lock:
            self._slewing = True
            self._slew_complete_event = asyncio.Event()

    def markSlewAsComplete(self):
        with self._lock:
            self._slewing = False
            if self._slew_complete_event:
                self._slew_complete_event.set()

    def markParkingAsUnderway(self):
        with self._lock:
            self._slewing = True
            self._atpark = False

    def markParkingAsComplete(self):
        with self._lock:
            self._slewing = False
            self._atpark = True

    def markParkingAsCanceled(self):
        with self._lock:
            self._pid.set_parking_complete_callback(None)
            self._slewing = False
            self._atpark = False

    async def SlewToAltAz(self, altitude, azimuth, isasync = True) -> None:
        a_alt = altitude
        a_az = azimuth
        a_ra, a_dec = self.altaz2radec(a_alt, a_az)
        await self.SlewToCoordinates(a_ra, a_dec, isasync)

    # ******* Advanced MPC control aware methods ********
    def RotateToRelativePositionAngle(self, rel_position_angle):
        self.logger.info(f"->> Polaris: Rotate Relative Observed   PositionAngle {deg2dms(self.positionangle)} PLUS {deg2dms(rel_position_angle)}")
        position_angle = self.positionangle + rel_position_angle
        self.RotateToAbsolutePositionAngle(position_angle)


    def RotateToAbsolutePositionAngle(self, position_angle):
        self.logger.info(f"->> Polaris: Rotate Absolute Observed   PositionAngle {deg2dms(position_angle)}")
        roll = self._sm.pa2roll(self._pid.alpha_sp[0], self._pid.alpha_sp[1], position_angle)
        self.RotateToRollAngle(roll)

    def RotateToRollAngle(self, roll):
        if Config.advanced_rotator and Config.advanced_control:
            self.logger.info(f"->> Polaris: Rotate Absolute Observed   RollAngle {deg2dms(roll)}")
            self.markRotateAsUnderway()
            self._pid.set_alpha_target({ "roll": roll })
            self._pid.set_rotate_complete_callback(self.markRotateAsComplete)
            self.logger.info(f"->> Polaris: Rotate Observed   rotating {self.rotating}")
        else:
            self.logger.warning(f"->> Polaris: Advanced Rotator is not enabled")

    def SyncToPositionAngle(self, position_angle):
        self.logger.info(f"->> Polaris: Sync Absolute Observed   PositionAngle {deg2dms(position_angle)}, Current {deg2dms(self.positionangle)}")
        roll = self._sm.pa2roll(self._pid.alpha_sp[0], self._pid.alpha_sp[1], position_angle)
        self.SyncToRoll(roll)

    def SyncToRoll(self, roll_angle):
        if Config.advanced_rotator and Config.advanced_control:
            self.logger.info(f"->> Polaris: Sync Absolute Observed   RollAngle {deg2dms(roll_angle)}, Current {deg2dms(self.roll)}")
            self._sm.sync_roll(roll_angle)
            position_angle,_ = self._sm.roll2pa(self._pid.alpha_sp[0], self._pid.alpha_sp[1], roll_angle)
            self._pid.alpha_sp[2] = roll_angle
            self._pid.delta_sp[2] = position_angle
        else:
            self.logger.warning(f"->> Polaris: Advanced Rotator is not enabled")

    async def SlewToCoordinates(self, rightascension, declination, isasync = True) -> None:
        inthefuture = Config.aiming_adjustment_time if Config.aiming_adjustment_enabled else 0
        a_ra = rightascension
        a_dec = declination
        a_alt, a_az = self.radec2altaz(a_ra, a_dec, inthefuture)
        self.logger.info(f"->> Polaris: GOTO Observed   RA {hr2hms(a_ra)}     Dec {deg2dms(a_dec)}")
        self.logger.info(f"->> Polaris: GOTO Observed   Az {deg2dms(a_az)}   Alt {deg2dms(a_alt)} ")
        with self._lock:
            self._targetrightascension = a_ra
            self._targetdeclination = a_dec
        if Config.advanced_alignment and Config.advanced_control:
            p_az, p_alt = self._sm.azalt_ascom2polaris(a_az, a_alt)         # Use Multi-Point Alignment model
        else:
            p_alt, p_az = self.altaz_ascom2polaris(a_alt, a_az)             # Use Single-Point Alignment model

        syncmsg = 'Multi-Point Alignment' if (Config.advanced_alignment and Config.advanced_control) else 'Single-Point Alignment'
        gotomsg = 'Advanced Control' if (Config.advanced_goto and Config.advanced_control) else 'Polaris Control'
        self.logger.info(f"->> Polaris: GOTO Predicted  Az {deg2dms(p_az)}   Alt {deg2dms(p_alt)} ({syncmsg}, {gotomsg})")

        if Config.advanced_goto and Config.advanced_control:
            self.markGotoAsUnderway()
            self._pid.set_alpha_target({ "az": a_az, "alt": a_alt })
            self._pid.set_goto_complete_callback(self.markGotoAsComplete)
            if not isasync:
                await self._goto_complete_event.wait()
        else:
            if isasync:
                    asyncio.create_task(self.send_cmd_goto_altaz(p_alt, p_az, istracking=True))
            else:
                await self.send_cmd_goto_altaz(p_alt, p_az, istracking=True)

    async def AbortSlew(self):
        await self.unpark()
        await self.stop_tracking()
        if Config.advanced_goto and Config.advanced_control:
            self.logger.info(f"Advanced Control: ABORT GOTO")
            await self.stop_all_axes()
        else:
            await self.send_cmd_goto_abort()


    async def move_axis(self, axis:int, rate:float, units="ASCOM"):
        if axis not in (0, 1, 2, 3, 4, 5):
            raise ValueError(f"Invalid axis index: {axis}. Must be 0 Az, 1 Alt, 2 Roll, 3 RA, 4 Dec, 5 PA.")
        motor = self._motors[axis % 3]
        if Config.advanced_control and Config.advanced_slewing:
            raw = motor._model.interpolate[units].toRAW(rate)
            dps = motor._model.interpolate["RAW"].toDPS(raw)
            self.markSlewAsUnderway()
            self._pid.set_alpha_axis_velocity(axis % 3, dps) if axis<3 else self._pid.set_delta_axis_velocity(axis % 3, dps)
            self._pid.set_slew_complete_callback(self.markSlewAsComplete)
        else:
            self.logger.info(f"->> Polaris: MOVE Az/Alt/Rot Axis {axis} Rate {rate} Units {units}")
            with self._lock:
                self._axis_ASCOM_slewing_rates[axis] = rate
                self._slewing = any(self._axis_ASCOM_slewing_rates)
            if not (self._tracking and Config.advanced_control and Config.advanced_tracking):
                await motor.set_motor_speed(rate, units)

    async def stop_all_axes(self):
        with self._lock:
            self._axis_ASCOM_slewing_rates = [0,0,0]
            self._slewing = False
        if Config.advanced_control:
            self.logger.info(f"Advanced Control: STOP all axes")
            self._pid.set_pid_mode("IDLE")
            self.markGotoAsComplete()
            self.markRotateAsComplete()
            self.markSlewAsComplete()
            self.markParkingAsCanceled()
        await self._motors[0].set_motor_speed(0, "DPS")
        await self._motors[1].set_motor_speed(0, "DPS")
        await self._motors[2].set_motor_speed(0, "DPS")

    async def stop_tracking(self):
        self._tracking = False
        if self._tracking_in_benro:
                await self.send_cmd_change_tracking_state(False)
        if self._pid.mode == "TRACK":
            self.logger.info(f"Advanced Control: STOP tracking")
            self._pid.set_tracking_off()

    async def start_tracking(self):
        self._tracking = True
        if Config.advanced_tracking and Config.advanced_control:
            self.logger.info(f"Advanced Control: START tracking")
            self._pid.set_tracking_on()
        else:
            # only send message if we are not tracking and not slewing
            if not self._tracking_in_benro and not self._slewing:
                await self.send_cmd_change_tracking_state(True)

    def pulse_guide(self, direction: int, duration: int):
        if Config.advanced_guiding and Config.advanced_control:
            if Config.log_pulse_guiding:
                self.logger.info(f"Pulse guide queued: direction {direction}, duration {duration}ms")
            self._pid.pulse_delta_axis(direction, duration)
            with self._lock:
                self._ispulseguiding = True                     # is reset in _pid.track_target when all done
        else:
            self.logger.warning(f"->> Polaris: Advanced Guiding is not enabled")

    async def findHome(self):
        if Config.advanced_control:
            self.logger.info(f"Advanced Control: Find HOME Position of telescope")
            await self.stop_tracking()
            self._pid.set_zeta_ref_to_home()
            self.markParkingAsCanceled()
            self._pid.set_pid_mode('HOMING')


    async def setPark(self):
        if Config.advanced_control:
            payload = {
                "m1_park": float(self._zeta_meas[0]),
                "m2_park": float(self._zeta_meas[1]),
                "m3_park": float(self._zeta_meas[2]),
            }
            Config.apply_changes(payload)
            Config.save_pilot_overrides()
            self.logger.info(f"Advanced Control: Set Park Position {payload}")

    async def park(self):
        with self._lock:
            self._adj_altitude = 0
            self._adj_azimuth = 0
        if Config.advanced_control:
            self.logger.info(f"Advanced Control: PARK telescope")
            self.markParkingAsUnderway()
            await self.stop_tracking()
            self._pid.set_zeta_ref_to_park()
            self._pid.set_pid_mode('PARKING')
            self._pid.set_parking_complete_callback(self.markParkingAsComplete)
        else:
            # Benro Polaris Park (reset axes)
            with self._lock:
                self._atpark = True
            self.resetAxes()

    async def unpark(self):
        with self._lock:
            self._pid.set_pid_mode('IDLE')
            self._atpark = False

    async def resetAxes(self):
        # Benro Polaris Park (reset axes)
        await self.stop_all_axes()
        await self.stop_tracking()
        await asyncio.sleep(1)
        await self.send_cmd_park()

