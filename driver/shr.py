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
from falcon import Request, Response, HTTPBadRequest
from logging import Logger
from config import Config


logger: Logger = None
#logger = None                   # Safe on Python 3.7 but no intellisense in VSCode etc.

_bad_title = 'Bad Alpaca Request'

# --------------------------
# Alpaca Device/Server Info
# --------------------------
# Static metadata not subject to configuration changes
class DeviceMetadata:
    """ Metadata describing the Alpaca Device/Server """
    Version = '1.0.0'              # Alpaca Version Number (based on https://semver.org/)
    VersionSynScan = '010000'      # Must be 6 digits for SynScan protocol
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

#
# Log the request as soon as the resource handler gets it so subsequent
# logged messages are in the right order. Logs PUT body as well.
#
ispollreq = re.compile('connected|utcdate|canslew|cansetpierside|canpulseguide|alignmentmode|cansetguiderates|slewing|sideofpier|siteelevation|sitelatitude|sitelongitude|siderealtime|declination|rightascension|azimuth|altitude|tracking|cansettracking|athome|atpark')

async def log_request(req: Request):
    if Config.supress_alpaca_polling_msgs and req.method=="GET" and ispollreq.search(req.path):
        return
    msg = f'{req.remote_addr} -> {req.method} {req.path}'
    if req.query_string != '':
        msg += f'?{req.query_string}'
    logger.info(msg)
    if req.method == 'PUT' and req.content_length != 0:
        logger.info(f'{req.remote_addr} -> {await req.get_media()}')

def log_response(req: Request, valuestr: str):
    if Config.supress_alpaca_polling_msgs and req.method=="GET" and ispollreq.search(req.path):
        return
    logger.info(f'{req.remote_addr} <- {valuestr}')

# ------------------------------------------------
# Incoming Pre-Logging and Request Quality Control
# ------------------------------------------------
class PreProcessRequest():
    """Decorator for responders that quality-checks an incoming request

    If there is a problem, this causes a ``400 Bad Request`` to be returned
    to the client, and logs the problem.

    """
    def __init__(self, maxdev):
        self.maxdev = maxdev
        """Initialize a ``PreProcessRequest`` decorator object.

        Args:
            maxdev: The maximun device number. If multiple instances of this device
                type are supported, this will be > 0.

        Notes:
            * Bumps the ServerTransactionID value and returns it in sequence
        """

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
        await log_request(req)                            # Log even a bad request
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
def bytes2hexascii(data):
    s_hex = ' '.join(('0'+hex(x)[2:])[-2:] for x in data)
    s_ascii = ''.join(chr(x) if 32 <= x <= 126 else '.' for x in data)
    return f"{s_hex}: {s_ascii}"

def deg2dms(decimal_degrees):
    # Determine the sign and work with the absolute value
    sign = '-' if decimal_degrees < 0 else '+'
    decimal_degrees = abs(decimal_degrees)
    degrees = int(decimal_degrees)                          # Extract degrees
    minutes_float = (decimal_degrees - degrees) * 60        # Extract minutes
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60                # Extract seconds
    
    return f"{sign}{degrees}°{minutes:02}'{seconds:05.2f}\""

def hr2hms(decimal_hr):
    degrees = int(decimal_hr)                          # Extract degrees
    minutes_float = (decimal_hr - degrees) * 60        # Extract minutes
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60                # Extract seconds
    return f"{degrees:02}h{minutes:02}m{seconds:05.2f}s"

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
