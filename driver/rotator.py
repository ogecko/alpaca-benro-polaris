# -*- coding: utf-8 -*-
#
# -----------------------------------------------------------------------------
# rotator.py - Alpaca API responders for rotator
#
# This module provides all the Alpaca REST API endpoints for the ASCOM driver
# It provides GET and PUT responders for all the ASCOM IRotator interface properties
# It provides PUT responders for all the ASCOM IRotator interface methods
# Any ASCOM business logic around checking arguments is also performed here
# It also returns all Exceptions as per the ASCOM standard
# See https://ascom-standards.org/Help/Developer/html/T_ASCOM_DeviceInterface_IRotatorV3.htm

# This module is stateless and relies on the Polaris Class to hold any state 
# information about the Polaris Device and its Connection
#
# -----------------------------------------------------------------------------
from falcon import Request, Response, before
from logging import Logger
from shr import PropertyResponse, MethodResponse, PreProcessRequest, get_request_field, to_bool
from exceptions import *        # Nothing but exception classes
import math
from polaris import Polaris
from shr import DeviceMetadata

logger: Logger = None
polaris: Polaris = None

# ----------------------------------------------------------------------
# Set our reference to the Polaris object (not at import time)
# ----------------------------------------------------------------------
def start_rotator(p: Polaris): 
    global polaris
    polaris = p

# ----------------------
# MULTI-INSTANCE SUPPORT
# ----------------------
# If this is > 0 then it means that multiple devices of this type are supported.
# Each responder on_get() and on_put() is called with a devnum parameter to indicate
# which instance of the device (0-based) is being called by the client. Leave this
# set to 0 for the simple case of controlling only one instance of this device type.
#
maxdev = 0                      # Single instance

# -----------
# DEVICE INFO
# -----------
# Static metadata not subject to configuration changes
class RotatorMetadata:
    """ Metadata describing the Rotator Device."""
    Name = DeviceMetadata.Description
    Version = DeviceMetadata.Version
    Description = 'Alpaca Rotator Emulator'
    DeviceType = 'Rotator'
    DeviceID = '508424eb-e1fb-4a9d-b5ac-9d7c60c9dd53' # https://guidgenerator.com/online-guid-generator.aspx
    Info = 'ASCOM Alpaca driver for the Benro Polaris Mount. Implements IRotatorV3.'
    MaxDeviceNumber = maxdev
    InterfaceVersion = 3

# --------------------
# RESOURCE CONTROLLERS
# --------------------

@before(PreProcessRequest(maxdev))
class action:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())


@before(PreProcessRequest(maxdev))
class commandblind:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())


@before(PreProcessRequest(maxdev))
class commandbool:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())


@before(PreProcessRequest(maxdev))
class commandstring:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())


# Connected, though common, is implemented in rotator.py
@before(PreProcessRequest(maxdev))
class description:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.Description, req)


@before(PreProcessRequest(maxdev))
class driverinfo:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.Info, req)


@before(PreProcessRequest(maxdev))
class interfaceversion:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.InterfaceVersion, req)


@before(PreProcessRequest(maxdev))
class driverversion:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.Version, req)


@before(PreProcessRequest(maxdev))
class name:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.Name, req)


@before(PreProcessRequest(maxdev))
class supportedactions:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse([], req)  # Not PropertyNotImplemented

@before(PreProcessRequest(maxdev))
class connected:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        client = await get_request_field('ClientID', req)      # Raises 400 bad request if missing
        is_conn = polaris.connectionquery(client)
        resp.text = await PropertyResponse(is_conn, req)

    async def on_put(self, req: Request, resp: Response, devnum: int):
        client = await get_request_field('ClientID', req)      # Raises 400 bad request if missing
        conn = to_bool(await get_request_field('Connected', req))   # Raises 400 Bad Request if str to bool fails
        try:
            polaris.connectionrequest(client, conn)
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,  DriverException(0x500, ex))
