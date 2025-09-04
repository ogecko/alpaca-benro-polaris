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
from shr import DeviceMetadata, LifecycleController

logger: Logger = None
polaris: Polaris = None

# ----------------------------------------------------------------------
# Set our reference to the Polaris object (not at import time)
# ----------------------------------------------------------------------
def start_rotator(p: Polaris, lifecyle: LifecycleController): 
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
    Name = 'Alpaca Benro Polaris Rotator'
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

@before(PreProcessRequest(maxdev,'log_alpaca_actions'))
class action:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class commandblind:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class commandbool:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class commandstring:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())


# Connected, though common, is implemented in rotator.py
@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class description:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.Description, req)


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class driverinfo:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.Info, req)


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class interfaceversion:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.InterfaceVersion, req)


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class driverversion:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.Version, req)


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class name:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.Name, req)


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class supportedactions:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse([], req)  # Not PropertyNotImplemented

@before(PreProcessRequest(maxdev,'log_alpaca_polling'))
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

@before(PreProcessRequest(maxdev,'log_alpaca_polling'))
class canreverse:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        resp.text = await PropertyResponse(True, req)

@before(PreProcessRequest(maxdev,'log_alpaca_polling'))
class reverse:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.rotator_reverse
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Rotator.Reverse failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        reverse = await get_request_field('Reverse', req)      # Raises 400 bad request if missing

        try:
            polaris.rotator_reverse = to_bool(reverse)                       # Same here
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Rotator.Reverse failed', ex))

@before(PreProcessRequest(maxdev,'log_alpaca_polling'))
class ismoving:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = bool(polaris._pid.is_deviating)
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Rotator.IsMoving failed', ex))


@before(PreProcessRequest(maxdev,'log_alpaca_polling'))
class position:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = round(polaris.roll,3)
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Rotator.Position failed', ex))


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class targetposition:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = round(polaris.roll,3)
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Rotator.TargetPosition failed', ex))


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class mechanicalposition:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = round(polaris.roll,3)
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Rotator.MechanicalPosition failed', ex))


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class movemechanical:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        positionstr = await get_request_field('Position', req)      # Raises 400 bad request if missing
        try:
            position = float(positionstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} not a valid number.'))
            return
        if position < -180 or position > 180 or math.isnan(position):
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} must be between -180 and +180.'))
            return
        try:
            polaris._pid.set_alpha_target({ "roll": position })
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Rotator.MoveMechanical failed', ex))

@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class moveabsolute:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        positionstr = await get_request_field('Position', req)      # Raises 400 bad request if missing
        try:
            position = float(positionstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} not a valid number.'))
            return
        if position < -180 or position > 180 or math.isnan(position):
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} must be between -180 and +180.'))
            return
        try:
            polaris._pid.set_alpha_target({ "roll": position })
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Rotator.MoveAbsolute failed', ex))


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class move:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        positionstr = await get_request_field('Position', req)      # Raises 400 bad request if missing
        try:
            position = float(positionstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} not a valid number.'))
            return
        if position < -180 or position > 360 or math.isnan(position):
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} must be between -180 and 360.'))
            return
        try:
            polaris._pid.rotator_move_relative(position)
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Rotator.Move failed', ex))

@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class stepsize:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())