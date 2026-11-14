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
from exceptions import NotImplementedException, DriverException, NotConnectedException, InvalidValueException, InvalidOperationException
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
    """Run a Device Action. The Rotator has none: the Alpaca Driver's Device Actions are on the Telescope."""
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class commandblind:
    """Send a raw command to the device. Not implemented."""
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class commandbool:
    """Send a raw command and return a boolean. Not implemented."""
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class commandstring:
    """Send a raw command and return a string. Not implemented."""
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())


# Connected, though common, is implemented in rotator.py
@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class description:
    """A description of the Rotator device."""
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.Description, req)


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class driverinfo:
    """Information about the driver, including the interface it implements (IRotatorV3)."""
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.Info, req)


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class interfaceversion:
    """The ASCOM Rotator interface version the driver implements: 3."""
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.InterfaceVersion, req)


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class driverversion:
    """The Alpaca Driver's version."""
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.Version, req)


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class name:
    """The Rotator's name, as shown in applications: Alpaca Benro Polaris Rotator."""
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(RotatorMetadata.Name, req)


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class supportedactions:
    """The Device Actions the Rotator supports: none (an empty list)."""
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse([], req)  # Not PropertyNotImplemented

@before(PreProcessRequest(maxdev,'log_alpaca_polling'))
class connected:
    """Whether this client is connected to the Rotator. Set `Connected` to true or false to connect or disconnect; each `ClientID` connects separately."""
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
    """Whether the Rotator supports reversing its direction: always true."""
    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        resp.text = await PropertyResponse(True, req)

@before(PreProcessRequest(maxdev,'log_alpaca_polling'))
class reverse:
    """Whether the Rotator's direction is reversed. Set with `Reverse`. The value is stored and reported, but the driver doesn't currently act on it."""
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
    """Whether the Rotator is rotating the camera."""
    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = bool(polaris.rotating)
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Rotator.IsMoving failed', ex))


@before(PreProcessRequest(maxdev,'log_alpaca_polling'))
class position:
    """The camera's Position Angle on the sky, in degrees: its angle relative to celestial north."""
    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            if polaris.positionangle is None:
                val = 0
            else:
                val = round(polaris.positionangle, 3)
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Rotator.Position failed', ex))


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class targetposition:
    """The Position Angle the Rotator is moving to, in degrees."""
    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            if polaris.targetpositionangle is None:
                val = 0
            else:
                val = round(polaris.targetpositionangle, 3)
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Rotator.TargetPosition failed', ex))


@before(PreProcessRequest(maxdev,'log_alpaca_polling'))
class mechanicalposition:
    """The camera's Roll Angle, in degrees: its angle relative to the horizon."""
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
    """Rotate the camera to a Roll Angle, given as `Position` in degrees (-180 to 360). Keeps the mount pointing at the same target. Needs Alpaca Rotator to be on in Alpaca Pilot's settings, and ends any sync guiding."""
    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        positionstr = await get_request_field('Position', req)      # Raises 400 bad request if missing
        try:
            position = float(positionstr)
        except Exception: 
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} not a valid number.'))
            return
        if position < -180 or position > 360 or math.isnan(position):
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} must be between -180 and +360.'))
            return
        try:
            polaris.RotateToRollAngle(position)
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Rotator.MoveMechanical failed', ex))

@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class moveabsolute:
    """Rotate the camera to a Position Angle, given as `Position` in degrees (-180 to 360). Keeps the mount pointing at the same target. Needs Alpaca Rotator to be on, and ends any sync guiding."""
    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        positionstr = await get_request_field('Position', req)      # Raises 400 bad request if missing
        try:
            position = float(positionstr)
        except Exception: 
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} not a valid number.'))
            return
        if position < -180 or position > 360 or math.isnan(position):
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} must be between -180 and +360.'))
            return
        try:
            polaris.RotateToAbsolutePositionAngle(position)
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Rotator.MoveAbsolute failed', ex))


@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class move:
    """Rotate the camera by `Position` degrees (-540 to 540), relative to its current Position Angle. Needs Alpaca Rotator to be on, and ends any sync guiding."""
    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        positionstr = await get_request_field('Position', req)      # Raises 400 bad request if missing
        try:
            position = float(positionstr)
        except Exception: 
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} not a valid number.'))
            return
        if position < -540 or position > +540 or math.isnan(position):
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} must be between -540 and 540.'))
            return
        try:
            polaris.RotateToRelativePositionAngle(position)
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Rotator.Move failed', ex))

@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class sync:
    """Tell the driver the camera's true Position Angle, given as `Position` in degrees (-180 to 360), for example from a plate solve. Adds a roll sync point to the Multi-Point Alignment model, so has no effect unless Multi-Point Alignment is on."""
    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        positionstr = await get_request_field('Position', req)      # Raises 400 bad request if missing
        try:
            position = float(positionstr)
        except Exception: 
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} not a valid number.'))
            return
        if position < -180 or position > 360 or math.isnan(position):
            resp.text = await MethodResponse(req, InvalidValueException(f'Position {positionstr} must be between -180 and 360.'))
            return
        try:
            polaris.SyncToPositionAngle(position)
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Rotator.Move failed', ex))

@before(PreProcessRequest(maxdev,'log_rotator_protocol'))
class stepsize:
    """The smallest rotation step, in degrees: one arc second (1/3600)."""
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(1/3600, req)

@before(PreProcessRequest(maxdev, 'log_rotator_protocol'))
class halt:
    """Stop rotating. This stops the whole mount, including any slew and tracking, the same as the Telescope's `abortslew`. Fails while the mount is parked."""

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        if polaris.atpark:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot Halt Rotator while parked'))
            return
        try:
            await polaris.AbortSlew()
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Abortslew failed', ex))
