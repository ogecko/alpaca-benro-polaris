# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# shr.py - Device characteristics and support classes/functions/data
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
# 15-Dec-2022   rbd 0.1 Initial edit for Alpaca sample/template
# 18-Dev-2022   rbd 0.1 Additional driver info items
# 20-Dec-2022   rbd 0.1 Fix idiotic error in to_bool()
# 22-Dec-2022   rbd 0.1 DeviceMetadata
# 24-Dec-2022   rbd 0.1 Logging
# 25-Dec-2022   rbd 0.1 Logging typing for intellisense
# 26-Dec-2022   rbd 0.1 Refactor logging to config module.
# 27-Dec-2022   rbd 0.1 Methods can return values. Common request
#                       logging (before starting processing).
#                       MIT license and module header. Logging cleanup.
#                       Python 3.7 global restriction.
# 28-Dec-2022   rbd 0.1 Rename conf.py to config.py to avoid conflict with sphinx
# 29-Dec-2022   rbd 0.1 ProProcess() Falcon hook class for pre-logging and
#                       common request validation (Client IDs for now).
# 31-Dec-2022   rbd 0.1 Bad boolean values return 400 Bad Request
# 10-Jan-2023   rbd 0.1 Cleanups for documentation and add docstrings for Sphinx.
# 23-May-2023   rbd 0.2 Refactoring for multiple ASCOM device type support
#               GitHub issue #1. Improve error messages in PreProcessRequest().
# 29-May-2023   rbd 0.2 Enhance get_request_field() so empty string for default
#               value means mandatory field. Add title and description info
#               to raised HTTP BAD_REQUEST.
# 30-May-2023   rbd 0.3 Improve request logging at time of arrival
# 01-Jun-2023   rbd 0.3 Issue #2 Do not return empty Value field in property
#               response, and omit Value if error is not success().

from threading import Lock
from exceptions import Success
import json
import re
import math
import asyncio
import threading
from falcon import Request, Response, HTTPBadRequest
from logging import Logger
from config import Config
import re
from typing import Set, Coroutine


logger: Logger = None
#logger = None                   # Safe on Python 3.7 but no intellisense in VSCode etc.

_bad_title = 'Bad Alpaca Request'

# --------------------------
# Alpaca Device/Server Info
# --------------------------
# Static metadata not subject to configuration changes
class DeviceMetadata:
    """ Metadata describing the Alpaca Device/Server """
    Version = '2.0.0'              # Alpaca Version Number (based on https://semver.org/)
    VersionSynScan = '020000'      # Must be 6 digits for SynScan protocol
    Description = 'Alpaca Benro Polaris Driver'
    Manufacturer = 'oGecko'


# ---------------
# Data Validation
# ---------------
_bools = ['true', 'false']                               # Only valid JSON bools allowed
def to_bool(str: str) -> bool:
    val = str.lower()
    if val not in _bools:
        raise HTTPBadRequest(title=_bad_title, description=f'Bad boolean value "{val}"')
    return val == _bools[0]

# ---------------------------------------------------------
# Get parameter/field from query string or body "form" data
# If default is missing then the field is required. Maybe the
# field name is smisspelled, or mis-cased (for PUT), or
# missing. In any case, raise a 400 BAD REQUEST. Optional
# caseless (mostly for the ClientID and ClientTransactionID)
# ---------------------------------------------------------
async def get_request_field(name: str, req: Request, caseless: bool = False, default: str = None) -> str:
    bad_desc = f'Missing, empty, or misspelled parameter "{name}"'
    lcName = name.lower()
    if req.method == 'GET':
        for param in req.params.items():        # [name,value] tuples
            if param[0].lower() == lcName:
                return param[1]
        if default == None:
            raise HTTPBadRequest(title=_bad_title, description=bad_desc)                # Missing or incorrect casing
        return default                          # not in args, return default
    else:                                       # Assume PUT since we never route other methods
        formdata = await req.get_media()
        if caseless:
            for fn in formdata.keys():
                if fn.lower() == lcName:
                    return formdata[fn]
        else:
            if name in formdata and formdata[name] != '':
                return formdata[name]
        if default == None:
            raise HTTPBadRequest(title=_bad_title, description=bad_desc)                # Missing or incorrect casing
        return default

# Should we log this HTTP req or response
def should_log(req: Request, log_flags): 
    for name in log_flags:
        if getattr(Config, name, False):
            return True  # explicitly enabled
        if req.method == 'PUT' and name == 'log_alpaca_polling' and Config.log_alpaca_protocol:
            return True  # allow polling logs on PUT even if disabled
    return False  # skip logging
#
# Log the request as soon as the resource handler gets it so subsequent
# logged messages are in the right order. Logs PUT body as well.
#
async def log_request(req: Request, log_flag_names: list[str] | str | None = None):
    # get log flags from optional argument or req.context
    if isinstance(log_flag_names, str):
        log_flags = [log_flag_names]
    else:
        log_flags = log_flag_names or getattr(req.context, 'log_flag_names', None)
    req.context.log_flag_names = log_flags   # Save for later use by log_response()

    if not should_log(req, log_flags):
        return   # skip logging

    msg = f'{req.remote_addr} -> {req.method} {req.path}'
    if req.query_string != '':
        msg += f'?{req.query_string}'
    if req.method == 'PUT' and req.content_length != 0:
        msg += f' {await req.get_media()}'
    logger.info(msg)

def log_response(req: Request, valuestr: str):
    log_flags = getattr(req.context, 'log_flag_names', None)
    if not should_log(req, log_flags):
        return   # skip logging

    logger.info(f'{req.remote_addr} <- {valuestr}')

# ------------------------------------------------
# Incoming Pre-Logging and Request Quality Control
# ------------------------------------------------
class PreProcessRequest():
    """Decorator for responders that quality-checks an incoming request and records logging requirements
    If there is a problem, this causes a ``400 Bad Request`` to be returned
    to the client, and logs the problem.

    """
    def __init__(self, maxdev, log_flag_names: list[str] | str | None = None):
        self.maxdev = maxdev
        if isinstance(log_flag_names, str):
            self.log_flag_names = [log_flag_names]
        else:
            self.log_flag_names = log_flag_names or []
    #
    # Quality check of numerical value for trans IDs
    #
    @staticmethod
    def _pos_or_zero(val: str) -> bool:
        try:
            test = int(val)
            return test >= 0
        except ValueError:
            return False

    async def _check_request(self, req: Request, devnum: int):  # Raise on failure
        if devnum > self.maxdev:
            msg = f'Device number {str(devnum)} does not exist. Maximum device number is {self.maxdev}.'
            logger.error(msg)
            raise HTTPBadRequest(title=_bad_title, description=msg)
        test = str(await get_request_field('ClientID', req, True))        # Caseless
        if not test:
            msg = 'Request has missing Alpaca ClientID value'
            logger.error(msg)
            raise HTTPBadRequest(title=_bad_title, description=msg)
        if not self._pos_or_zero(test):
            msg = f'Request has bad Alpaca ClientID value {test}'
            logger.error(msg)
            raise HTTPBadRequest(title=_bad_title, description=msg)
        test  = str(await get_request_field('ClientTransactionID', req, True))
        if not self._pos_or_zero(test):
            msg = f'Request has bad Alpaca ClientTransactionID value {test}'
            logger.error(msg)
            raise HTTPBadRequest(title=_bad_title, description=msg)

    #
    # params contains {'devnum': n } from the URI template matcher
    # and format converter. This is the device number from the URI
    #
    async def __call__(self, req: Request, resp: Response, resource, params):
        req.context.log_flag_names = self.log_flag_names   # For use by log_request() and log_response()
        await log_request(req)                             # Log even a bad request
        await self._check_request(req, params['devnum'])   # Raises to 400 error on check failure

# ------------------
# PropertyResponse
# ------------------
async def PropertyResponse(value, req: Request, err = Success()):
    """Form a ``PropertyResponse`` string.

    Args:
        value:  The value of the requested property, or None if there was an
            exception.
        req: The Falcon Request property that was provided to the responder.
        err: An Alpaca exception class as defined in the exceptions
            or defaults to :py:class:`~exceptions.Success`

    Notes:
        * Bumps the ServerTransactionID value and returns it in sequence
    """
    res = {
        "ServerTransactionID": getNextTransId(),
        "ClientTransactionID": int(await get_request_field('ClientTransactionID', req, False, 0)),  #Caseless on GET
        "ErrorNumber": err.Number,
        "ErrorMessage": err.Message
    }
    if err.Number == 0 and not value is None:
        res["Value"] = value
        log_response(req, str(value))

    return json.dumps(res)

# --------------
# MethodResponse
# --------------
async def MethodResponse(req: Request, err = Success(), value = None): # value useless unless Success
    """Initialize a MethodResponse string.

    Args:
        req: The Falcon Request property that was provided to the responder.
        err: An Alpaca exception class as defined in the exceptions or defaults to :py:class:`~exceptions.Success`
        value:  If method returns a value, or defaults to None

    Notes:
        * Bumps the ServerTransactionID value and returns it in sequence
    """
    res = {
        "ServerTransactionID": getNextTransId(),
        "ClientTransactionID": int(await get_request_field('ClientTransactionID', req, False, 0)),
        "ErrorNumber": err.Number,
        "ErrorMessage": err.Message
    }
    if err.Number == 0 and not value is None:
        res["Value"] = value
        logger.info(f'{req.remote_addr} <- {str(value)}')

    return json.dumps(res)


# -------------------------------
# Thread-safe ServerTransactionID
# -------------------------------
_lock = Lock()
_stid = 0

def getNextTransId() -> int:
    with _lock:
        global _stid
        _stid += 1
    return _stid


# -------------------------------
# Number conversion functions
# -------------------------------
def clamparcsec(x):
    try:
        value = float(x) % (360 * 3600)  # Normalize to 0-360 degrees in arc-seconds
        if value > 180 * 3600:
            value -= 360 * 3600  # Adjust to -180 to 180 degrees in arc-seconds
        elif value < -180 * 3600:
            value += 360 * 3600  # Adjust to -180 to 180 degrees in arc-seconds
        return value
    except ValueError:
        return float('nan')


def bytes2hexascii(data):
    s_hex = ' '.join(('0'+hex(x)[2:])[-2:] for x in data)
    s_ascii = ''.join(chr(x) if 32 <= x <= 126 else '.' for x in data)
    return f"{s_hex}: {s_ascii}"

def deg2dms(decimal_degrees):
    """Converts decimal degrees to formatted degrees-minutes-seconds (DMS) string with sign."""
    sign = '-' if decimal_degrees < 0 else '+'
    total_seconds = abs(decimal_degrees) * 3600
    degrees, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    seconds = round(seconds, 2) # Beware of rounding to 60.00
    if seconds >= 60.0:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        degrees += 1
    return f"{sign}{int(degrees):03}d{int(minutes):02}'{seconds:05.2f}\""

def hr2hms(decimal_hr):
    """Converts decimal hours to formatted hours-minutes-seconds (HMS) string."""
    sign = "-" if decimal_hr < 0 else ""
    decimal_seconds = abs(decimal_hr) * 3600
    hours, remainder = divmod(decimal_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    seconds = round(seconds, 2) # Beware of rounding to 60.00
    if seconds >= 60.0:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        hours += 1
    return f"{sign}{int(hours):02}h{int(minutes):02}m{seconds:05.2f}s"

def dms2dec(dms):
    """Parses a DMS string into decimal degrees."""
    parts = re.split(r'[^\d.-]+', dms)
    parts = [float(p) for p in parts if p]
    if not parts:
        raise ValueError(f"dms2dec: Invalid HMS string input: '{dms}'")
    while len(parts) < 3:
        parts.append(0.0)
    sign = 1 if parts[0] >= 0 else -1
    degrees, minutes, seconds = abs(parts[0]), parts[1], parts[2]
    total_deg = degrees + minutes / 60 + seconds / 3600 
    return sign * total_deg

def dms2rad(dms):
    """Converts DMS formatted string (e.g. '+123d45\'56.78"') to radians."""
    return deg2rad(dms2dec(dms))

def rad2dms(rad):
    """Converts radians to DMS formatted string (e.g. '+123d45\'56.78"')."""
    return deg2dms(rad2deg(rad))

def hms2hr(hms):
    """Converts HMS formatted string to decimal hours."""
    parts = re.split(r'[^0-9.]+', hms)
    parts = [float(p) for p in parts if p]  # Remove empty entries
    if not parts or len(parts) < 1:
        raise ValueError(f"dms2dec: Invalid HMS string input: '{hms}'")
    while len(parts) < 3:
        parts.append(0.0)
    hours, minutes, seconds = parts[0], parts[1], parts[2]
    return hours + minutes / 60 + seconds / 3600

def hms2rad(hms):
    """Converts HMS formatted string (e.g. '12h30m00s') to radians."""
    return hr2rad(hms2hr(hms))

def rad2hms(rad):
    """Converts radians to HMS formatted string using hr2hms."""
    return hr2hms(rad2hr(rad))

def rad2hr(rad):
    """Converts radians to hours (assuming 2π radians = 24 hours)."""
    return rad*12/math.pi

def hr2rad(hr):
    """Converts hours to radians."""
    return hr*math.pi/12

def rad2deg(rad):
    """Converts radians to decimal degrees."""
    return rad*180/math.pi

def deg2rad(deg):
    """Converts decimal degrees to radians."""
    return deg*math.pi/180

def empty_queue(q: asyncio.Queue):
  while not q.empty():
    try:
        q.get_nowait()
    except asyncio.QueueEmpty:
        break

from enum import Enum, auto

class LifecycleEvent(Enum):
    NONE = auto()
    SHUTDOWN = auto()           # shutdown the process
    RESTART = auto()            # restart all network services and running async tasks
    INTERRUPT = auto()          # user initiated shutdown ^C
    START = auto()              # used initated start of a stopable procedure
    STOP = auto()               # user initiated stop of a procedure
    
class LifecycleController:
    def __init__(self):
        self._event = LifecycleEvent.NONE
        self._cond = asyncio.Condition()
        self._lock = threading.Lock()  # For thread-safe sync signaling
        self._tasks: Set[asyncio.Task] = set()

    def create_task(self, coro: Coroutine, *, name: str = None) -> asyncio.Task:
        task = asyncio.create_task(self._wrap(coro), name=name)
        self._tasks.add(task)
        task.add_done_callback(self._done_task)
        return task

    def _done_task(self, task: asyncio.Task):
        self._tasks.discard(task)  # Remove completed task from the set

    async def _wrap(self, coro: Coroutine):
        try:
            await coro
        except asyncio.CancelledError:
            logger.debug("Lifecycle Wrap: Task cancelled")
        except SystemExit as exc:
            logger.error(f"Lifecycle Wrap: Task SystemExit: {exc}")
            raise RuntimeError("SystemExit in task") from exc
        except Exception as exc:
            co_name = coro.cr_code.co_name
            logger.exception(f"Lifecycle Wrap: Task {co_name} Unhandled exception: {exc}")

    async def shutdown_tasks(self, timeout: float = 5.0):
        if self._event == LifecycleEvent.NONE:
            await self.signal(LifecycleEvent.SHUTDOWN)
        for task in list(self._tasks):
            task.cancel()
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("==SHUTDOWN==Timeout while waiting for tasks to cancel")
        pending = [t for t in self._tasks if not t.done()]
        if pending:
            logger.warning(f"==SHUTDOWN==Tasks still pending: {pending}")


    def should_stop(self) -> bool:
        return self._event in {LifecycleEvent.RESTART, LifecycleEvent.SHUTDOWN, LifecycleEvent.INTERRUPT, LifecycleEvent.STOP}

    def should_shutdown(self) -> bool:
        return self._event in {LifecycleEvent.RESTART, LifecycleEvent.SHUTDOWN, LifecycleEvent.INTERRUPT}

    async def wait_for_event(self):
        async with self._cond:
            await self._cond.wait()
            return self._event

    async def signal(self, event: LifecycleEvent):
        async with self._cond:
            self._event = event
            self._cond.notify_all()

    def signal_sync(self, event: LifecycleEvent):
        # Called from signal handlers (e.g., SIGINT)
        with self._lock:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(self._set_event_and_notify, event)

    def _set_event_and_notify(self, event: LifecycleEvent):
        # Internal helper for thread-safe signaling
        async def notify():
            async with self._cond:
                self._event = event
                self._cond.notify_all()
        asyncio.create_task(notify())

    def start(self):
        self._event = LifecycleEvent.START

    def stop(self):
        self._event = LifecycleEvent.STOP

    def reset(self):
        self._event = LifecycleEvent.NONE
