
# -*- coding: utf-8 -*-
#
# -----------------------------------------------------------------------------
# telescope.py - Alpaca API responders for Telescope
#
# This module provides all the Alpaca REST API endpoints for the ASCOM driver
# It provides GET and PUT responders for all the ASCOM ITelescope interface properties
# It provides PUT responders for all the ASCOM ITelescope interface methods
# Any ASCOM business logic around checking arguments is also performed here
# It also returns all Exceptions as per the ASCOM standard
# See https://ascom-standards.org/Help/Developer/html/T_ASCOM_DeviceInterface_ITelescopeV3.htm

# This module is stateless and relies on the Polaris Class to hold any state 
# information about the Polaris Device and its Connection
#
# -----------------------------------------------------------------------------
from falcon import Request, Response, before
import asyncio
from logging import Logger
from shr import PropertyResponse, MethodResponse, HTTPBadRequest,  PreProcessRequest, get_request_field, to_bool, deg2rad
from exceptions import *        # Nothing but exception classes
import math
import json
from polaris import Polaris
from shr import DeviceMetadata, LifecycleController, LifecycleEvent
from log import update_log_level

logger: Logger = None
polaris: Polaris = None
lifecycle: LifecycleController = None

# ----------------------------------------------------------------------
# Set our reference to the Polaris object (not at import time)
# ----------------------------------------------------------------------
def start_telescope(p: Polaris, lf: LifecycleController): 
    global polaris
    polaris = p
    global lifecycle
    lifecycle = lf

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
class TelescopeMetadata:
    """ Metadata describing the Telescope Device."""
    Name = 'Alpaca Benro Polaris Telescope' 
    Version = DeviceMetadata.Version
    Description = 'Alpaca Telescope Mount'
    DeviceType = 'Telescope'
    DeviceID = '3ee8e486-6421-432c-9a66-cf240e298bb9' # https://guidgenerator.com/online-guid-generator.aspx
    Info = 'ASCOM Alpaca driver for the Benro Polaris Mount. Implements ITelescopeV3.'
    MaxDeviceNumber = maxdev
    InterfaceVersion = 3


    
# --------------------
# RESOURCE CONTROLLERS
# --------------------

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class commandblind:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class commandbool:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class commandstring:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class dispose:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class findhome:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class destinationsideofpier:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        rightascensionstr = await get_request_field('RightAscension', req)  # Raises 400 bad request if missing
        try:
            rightascension = float(rightascensionstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'RightAscension {rightascensionstr} not a valid number.'))
            return
        if rightascension < 0 or rightascension > 24 or math.isnan(rightascension):
            resp.text = await MethodResponse(req, InvalidValueException(f'RightAscension {rightascensionstr} must be between 0 and 24.'))
            return
        declinationstr = await get_request_field('Declination', req)      # Raises 400 bad request if missing
        try:
            declination = float(declinationstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} not a valid number.'))
            return
        if declination < -90 or declination > +90 or math.isnan(declination):
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} must be between -90 and +90.'))
            return
        resp.text = await PropertyResponse(0, req)

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
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

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class description:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(TelescopeMetadata.Description, req)

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class driverinfo:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(TelescopeMetadata.Info, req)

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class interfaceversion:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(TelescopeMetadata.InterfaceVersion, req)

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class driverversion():
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(TelescopeMetadata.Version, req)

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class name():
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(TelescopeMetadata.Name, req)


@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class alignmentmode:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.alignmentmode
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Alignmentmode failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class altitude:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.altitude
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Altitude failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class aperturearea:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.aperturearea
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Aperturearea failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class aperturediameter:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.aperturediameter
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Aperturediameter failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class athome:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.athome
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Athome failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class atpark:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.atpark
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Atpark failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class azimuth:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.azimuth
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Azimuth failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class canfindhome:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.canfindhome
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Canfindhome failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class canpark:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.canpark
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Canpark failed', ex))

@before(PreProcessRequest(maxdev, 'log_pulse_guiding'))
class canpulseguide:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.canpulseguide
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Canpulseguide failed', ex))

@before(PreProcessRequest(maxdev, 'log_pulse_guiding'))
class cansetguiderates:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.cansetguiderates
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Cansetguiderates failed', ex))

@before(PreProcessRequest(maxdev, 'log_pulse_guiding'))
class cansetrightascensionrate:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.cansetrightascensionrate
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Cansetrightascensionrate failed', ex))

@before(PreProcessRequest(maxdev, 'log_pulse_guiding'))
class cansetdeclinationrate:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.cansetdeclinationrate
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Cansetdeclinationrate failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class cansetpark:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.cansetpark
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Cansetpark failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class cansetpierside:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.cansetpierside
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Cansetpierside failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class cansettracking:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.cansettracking
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Cansettracking failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class canslew:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.canslew
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Canslew failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class canslewaltaz:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.canslewaltaz
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Canslewaltaz failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class canslewaltazasync:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.canslewaltazasync
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Canslewaltazasync failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class canslewasync:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.canslewasync
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Canslewasync failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class cansync:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.cansync
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Cansync failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class cansyncaltaz:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.cansyncaltaz
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Cansyncaltaz failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class canunpark:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.canunpark
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Canunpark failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class declination:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.declination
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Declination failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class declinationrate:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.declinationrate
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Declinationrate failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class doesrefraction:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.doesrefraction
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Doesrefraction failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        doesrefractionstr = await get_request_field('DoesRefraction', req)      # Raises 400 bad request if missing

        try:
            polaris.doesrefraction = to_bool(doesrefractionstr)                       # Same here
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Doesrefraction failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class equatorialsystem:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.equatorialsystem
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Equatorialsystem failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class focallength:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.focallength
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Focallength failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class guideratedeclination:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.guideratedeclination
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Guideratedeclination failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class guideraterightascension:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.guideraterightascension
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Guideraterightascension failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())

@before(PreProcessRequest(maxdev), 'log_pulse_guiding')
class ispulseguiding:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())
        return
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.ispulseguiding
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.ispulseguiding failed', ex))

        # resp.text = await MethodResponse(req, NotImplementedException())

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class rightascension:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.rightascension
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Rightascension failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class rightascensionrate:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.rightascensionrate
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Rightascensionrate failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class sideofpier:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.sideofpier
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Sideofpier failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        sideofpierstr = await get_request_field('SideOfPier', req)      # Raises 400 bad request if missing
        try:
            polaris.sideofpier = int(sideofpierstr)
        except:
            resp.text = await MethodResponse(req,
                            InvalidValueException(f'SideOfPier {sideofpierstr} not a valid number.'))
            return
        ### RANGE CHECK AS NEEDED ###          # Raise Alpaca InvalidValueException with details!
        try:
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Sideofpier failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class siderealtime:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.siderealtime
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Siderealtime failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class siteelevation:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.siteelevation
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Siteelevation failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        siteelevationstr = await get_request_field('SiteElevation', req)      # Raises 400 bad request if missing
        try:
            siteelevation = float(siteelevationstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'SiteElevation {siteelevationstr} not a valid number.'))
            return
        if siteelevation < 0 or siteelevation > 10000 or math.isnan(siteelevation):
            resp.text = await MethodResponse(req, InvalidValueException(f'SiteElevation {siteelevationstr} must be between 0 and 10000.'))
            return
        try:
            polaris.siteelevation = siteelevation
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.Siteelevation failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class sitelatitude:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.sitelatitude
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Sitelatitude failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        sitelatitudestr = await get_request_field('SiteLatitude', req)      # Raises 400 bad request if missing
        try:
            sitelatitude = float(sitelatitudestr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'SiteLatitude {sitelatitudestr} not a valid number.'))
            return
        if sitelatitude < -90 or sitelatitude > 90 or math.isnan(sitelatitude):
            resp.text = await MethodResponse(req, InvalidValueException(f'SiteLatitude {sitelatitudestr} must be between -90 and 90.'))
            return
        try:
            polaris.sitelatitude = sitelatitude
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.Sitelatitude failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class sitelongitude:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.sitelongitude
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Sitelongitude failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        sitelongitudestr = await get_request_field('SiteLongitude', req)      # Raises 400 bad request if missing
        try:
            sitelongitude = float(sitelongitudestr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'SiteLongitude {sitelongitudestr} not a valid number.'))
            return
        if sitelongitude < -180 or sitelongitude > 180 or math.isnan(sitelongitude):
            resp.text = await MethodResponse(req, InvalidValueException(f'SiteLongitude {sitelongitudestr} must be between -180 and 180.'))
            return
        try:
            polaris.sitelongitude = sitelongitude
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.Sitelongitude failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class slewing:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.slewing
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Slewing failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class slewsettletime:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.slewsettletime
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Slewsettletime failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        slewsettletimestr = await get_request_field('SlewSettleTime', req)      # Raises 400 bad request if missing
        try:
            slewsettletime = int(slewsettletimestr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'SlewSettleTime {slewsettletimestr} not a valid number.'))
            return
        if slewsettletime < 0 or slewsettletime > 200:
            resp.text = await MethodResponse(req, InvalidValueException(f'SlewSettleTime {slewsettletimestr} must be between 0 and 200.'))
            return
        try:
            polaris.slewsettletime = slewsettletime
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.slewsettletime failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class targetdeclination:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        if polaris.targetdeclination == None:
            resp.text = await PropertyResponse(None, req, InvalidOperationException())
            return
        try:
            val = polaris.targetdeclination
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Targetdeclination failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        targetdeclinationstr = await get_request_field('TargetDeclination', req)      # Raises 400 bad request if missing
        try:
            targetdeclination = float(targetdeclinationstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'TargetDeclination {targetdeclinationstr} not a valid number.'))
            return
        if targetdeclination < -90 or targetdeclination > +90 or math.isnan(targetdeclination):
            resp.text = await MethodResponse(req, InvalidValueException(f'TargetDeclination {targetdeclinationstr} must be between -90 and +90.'))
            return
        try:
            polaris.targetdeclination = targetdeclination
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.targetdeclination failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class targetrightascension:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        if polaris.targetrightascension == None:
            resp.text = await PropertyResponse(None, req, InvalidOperationException())
            return
        try:
            val = polaris.targetrightascension
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Targetrightascension failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        targetrightascensionstr = await get_request_field('TargetRightAscension', req)      # Raises 400 bad request if missing
        try:
            targetrightascension = float(targetrightascensionstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'TargetRightAscension {targetrightascensionstr} not a valid number.'))
            return
        if targetrightascension < 0 or targetrightascension > 24 or math.isnan(targetrightascension):
            resp.text = await MethodResponse(req, InvalidValueException(f'TargetRightAscension {targetrightascensionstr} must be between 0 and 24.'))
            return
        try:
            polaris.targetrightascension = targetrightascension
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.targetrightascension failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class tracking:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.tracking
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Tracking failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        trackingstr = await get_request_field('Tracking', req)      # Raises 400 bad request if missing
        tracking = to_bool(trackingstr)

        try:
            if tracking:
                await polaris.start_tracking()
            else:
                await polaris.stop_tracking()

            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.Tracking failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class trackingrate:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.trackingrate
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Trackingrate failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        trackingratestr = await get_request_field('TrackingRate', req)      # Raises 400 bad request if missing
        try:
            trackingrate = int(trackingratestr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'TrackingRate {trackingratestr} not a valid number.'))
            return
        if trackingrate < 0 or trackingrate > 3:
            resp.text = await MethodResponse(req, InvalidValueException(f'TrackingRate {trackingrate} must be between 0 and 3.'))
            return
        try:
            polaris.trackingrate = trackingrate
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.Tracking failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class trackingrates:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.trackingrates
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Trackingrates failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class utcdate:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.utcdate
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Utcdate failed', ex))

    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(None, req, NotImplementedException())
        return

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class abortslew:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        if polaris.atpark:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot abort slew while parked'))
            return
        try:
            await polaris.AbortSlew()
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Abortslew failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class axisrates:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        axisstr = await get_request_field('Axis', req)      # Raises 400 bad request if missing
        try:
            axis = int(axisstr)
        except:
            resp.text = await PropertyResponse(None,req,InvalidValueException(f'Axis {axisstr} not a valid number.'))
            return
        try:
            val = polaris.axisrates
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Axisrates failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class canmoveaxis:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        axisstr = await get_request_field('Axis', req)      # Raises 400 bad request if missing
        try:
            axis = int(axisstr)
        except:
            resp.text = await PropertyResponse(None,req,InvalidValueException(f'Axis {axisstr} not a valid number.'))
            return
        if axis < 0 or axis > 2:
            resp.text = await PropertyResponse(None,req, InvalidValueException(f'Axis {axisstr} must be between 0 and 2.'))
            return
        try:
            val = polaris.canmoveaxis[axis]
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.Canmoveaxis failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_polling'))
class sideofpier:

    async def on_get(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            val = polaris.sideofpier
            resp.text = await PropertyResponse(val, req)
        except Exception as ex:
            resp.text = await PropertyResponse(None, req, DriverException(0x500, 'Telescope.sideofpier failed', ex))
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(None, req, NotImplementedException())
        return

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class moveaxis:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        if polaris.atpark:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot move axis while parked'))
            return
        axisstr = await get_request_field('Axis', req)      # Raises 400 bad request if missing
        try:
            axis = int(axisstr)
        except:
            resp.text = await MethodResponse(req,
                            InvalidValueException(f'Axis {axisstr} not a valid number.'))
            return
        if axis < 0 or axis > 2:
            resp.text = await PropertyResponse(None,req, InvalidValueException(f'Axis {axisstr} must be between 0 and 2.'))
            return
        ratestr = await get_request_field('Rate', req)      # Raises 400 bad request if missing
        try:
            rate = float(ratestr)
        except:
            resp.text = await MethodResponse(req,
                            InvalidValueException(f'Rate {ratestr} not a valid number.'))
            return
        if (rate != 0 and abs(rate) < polaris.axisrates[0]['Minimum']) or abs(rate) > polaris.axisrates[0]['Maximum'] or math.isnan(rate):
            resp.text = await PropertyResponse(None,req, InvalidValueException(f"rate {ratestr} must be between {polaris.axisrates[0]['Minimum']} and {polaris.axisrates[0]['Maximum']}."))
            return
        if polaris.gotoing and rate != 0:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot move while goto co-ordinates'))
            return
        try:
            await polaris.move_axis(axis, rate)
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Moveaxis failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class park:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            await polaris.park()
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Park failed', ex))

@before(PreProcessRequest(maxdev, 'log_pulse_guiding'))
class pulseguide:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())
        return
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        directionstr = await get_request_field('Direction', req)      # Raises 400 bad request if missing
        try:
            direction = int(directionstr)
        except:
            resp.text = await MethodResponse(req,
                            InvalidValueException(f'Direction {directionstr} not a valid number.'))
            return
        ### RANGE CHECK AS NEEDED ###          # Raise Alpaca InvalidValueException with details!
        durationstr = await get_request_field('Duration', req)      # Raises 400 bad request if missing
        try:
            duration = int(durationstr)
        except:
            resp.text = await MethodResponse(req,
                            InvalidValueException(f'Duration {durationstr} not a valid number.'))
            return
        ### RANGE CHECK AS NEEDED ###          # Raise Alpaca InvalidValueException with details!
        try:
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Pulseguide failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class setpark:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Setpark failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class slewtoaltaz:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        azimuthstr = await get_request_field('Azimuth', req)      # Raises 400 bad request if missing
        try:
            azimuth = float(azimuthstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Azimuth {azimuthstr} not a valid number.'))
            return
        if azimuth < 0 or azimuth > +360 or math.isnan(azimuth):
            resp.text = await MethodResponse(req, InvalidValueException(f'Azimuth {azimuthstr} must be between 0 and 360.'))
            return
        altitudestr = await get_request_field('Altitude', req)      # Raises 400 bad request if missing
        try:
            altitude = float(altitudestr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Altitude {altitudestr} not a valid number.'))
            return
        if altitude < -8 or altitude > +90 or math.isnan(altitude):
            resp.text = await MethodResponse(req, InvalidValueException(f'Altitude {altitudestr} must be between -8 and 90.'))
            return
        if polaris.atpark:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot slew while parked'))
            return
        if polaris.slewing:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot slew while slewing'))
            return
        try:
            await polaris.SlewToAltAz(altitude, azimuth, isasync=False)
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.Slewtoaltaz failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class slewtoaltazasync:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        azimuthstr = await get_request_field('Azimuth', req)      # Raises 400 bad request if missing
        try:
            azimuth = float(azimuthstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Azimuth {azimuthstr} not a valid number.'))
            return
        if azimuth < 0 or azimuth > +360 or math.isnan(azimuth):
            resp.text = await MethodResponse(req, InvalidValueException(f'Azimuth {azimuthstr} must be between 0 and 360.'))
            return
        altitudestr = await get_request_field('Altitude', req)      # Raises 400 bad request if missing
        try:
            altitude = float(altitudestr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Altitude {altitudestr} not a valid number.'))
            return
        if altitude < -8 or altitude > +90 or math.isnan(altitude):
            resp.text = await MethodResponse(req, InvalidValueException(f'Altitude {altitudestr} must be between -8 and 90.'))
            return
        if polaris.atpark:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot slew while parked'))
            return
        try:
            await polaris.SlewToAltAz(altitude, azimuth, isasync=True)
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.Slewtoaltazasync failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class slewtocoordinates:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        rightascensionstr = await get_request_field('RightAscension', req)      # Raises 400 bad request if missing
        try:
            rightascension = float(rightascensionstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'RightAscension {rightascensionstr} not a valid number.'))
            return
        if rightascension < 0 or rightascension > 24 or math.isnan(rightascension):
            resp.text = await MethodResponse(req, InvalidValueException(f'RightAscension {rightascensionstr} must be between 0 and 24.'))
            return
        declinationstr = await get_request_field('Declination', req)      # Raises 400 bad request if missing
        try:
            declination = float(declinationstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} not a valid number.'))
            return
        if declination < -90 or declination > +90 or math.isnan(declination):
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} must be between -90 and +90.'))
            return
        if polaris.atpark:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot slew while parked'))
            return
        if polaris.slewing:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot slew while slewing'))
            return
        try:
            await polaris.SlewToCoordinates(rightascension, declination, isasync=False)
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.Slewtocoordinates failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class slewtocoordinatesasync:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        rightascensionstr = await get_request_field('RightAscension', req)      # Raises 400 bad request if missing
        try:
            rightascension = float(rightascensionstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'RightAscension {rightascensionstr} not a valid number.'))
            return
        if rightascension < 0 or rightascension > 24 or math.isnan(rightascension):
            resp.text = await MethodResponse(req, InvalidValueException(f'RightAscension {rightascensionstr} must be between 0 and 24.'))
            return
        declinationstr = await get_request_field('Declination', req)      # Raises 400 bad request if missing
        try:
            declination = float(declinationstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} not a valid number.'))
            return
        if declination < -90 or declination > +90 or math.isnan(declination):
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} must be between -90 and +90.'))
            return
        if polaris.atpark:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot slew while parked'))
            return
        try:
            await polaris.SlewToCoordinates(rightascension, declination, isasync=True)
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.Slewtocoordinatesasync failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class slewtotarget:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        if polaris.atpark:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot slew while parked'))
            return
        if polaris.slewing:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot slew while slewing'))
            return
        try:
            await polaris.SlewToCoordinates(polaris.targetrightascension, polaris.targetdeclination, isasync=False)
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Slewtotarget failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class slewtotargetasync:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        if polaris.atpark:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot slew while parked'))
            return
        try:
            await polaris.SlewToCoordinates(polaris.targetrightascension, polaris.targetdeclination, isasync=True)
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Slewtotargetasync failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class synctoaltaz:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        azimuthstr = await get_request_field('Azimuth', req)      # Raises 400 bad request if missing
        try:
            azimuth = float(azimuthstr)
        except:
            resp.text = await MethodResponse(req,
                            InvalidValueException(f'Azimuth {azimuthstr} not a valid number.'))
            return
        if azimuth < 0 or azimuth > 360 or math.isnan(azimuth):
            resp.text = await MethodResponse(req, InvalidValueException(f'Azimuth {azimuthstr} must be between 0 and 360.'))
            return
        altitudestr = await get_request_field('Altitude', req)      # Raises 400 bad request if missing
        try:
            altitude = float(altitudestr)
        except:
            resp.text = await MethodResponse(req,
                            InvalidValueException(f'Altitude {altitudestr} not a valid number.'))
            return
        if altitude < -90 or altitude > 90 or math.isnan(altitude):
            resp.text = await MethodResponse(req, InvalidValueException(f'Altitude {altitudestr} must be between -90 and +90.'))
            return
        try:
            await polaris.sync_to_azalt(azimuth, altitude)
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Synctoaltaz failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class synctocoordinates:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        if polaris.atpark:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot sync to coordinates while parked.'))
            return
        rightascensionstr = await get_request_field('RightAscension', req)      # Raises 400 bad request if missing
        try:
            rightascension = float(rightascensionstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'RightAscension {rightascensionstr} not a valid number.'))
            return
        if rightascension < 0 or rightascension > 24 or math.isnan(rightascension):
            resp.text = await MethodResponse(req, InvalidValueException(f'RightAscension {rightascensionstr} must be between 0 and 24.'))
            return
        declinationstr = await get_request_field('Declination', req)      # Raises 400 bad request if missing
        try:
            declination = float(declinationstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} not a valid number.'))
            return
        if declination < -90 or declination > +90 or math.isnan(declination):
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} must be between -90 and +90.'))
            return
        try:
            await polaris.sync_to_radec(rightascension, declination)
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Synctocoordinates failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class synctotarget:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        if polaris.atpark:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot sync to target while parked'))
            return
        try:
            await polaris.sync_to_radec(polaris.targetrightascension, polaris.targetdeclination)
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Synctotarget failed', ex))

@before(PreProcessRequest(maxdev, 'log_alpaca_protocol'))
class unpark:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            await polaris.unpark()
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Unpark failed', ex))


@before(PreProcessRequest(maxdev, 'log_alpaca_discovery'))
class supportedactions:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse([
            "Polaris:bleSelectDevice", "Polaris:bleEnableWifi", 
            "Polaris:DeviceConnect", "Polaris:DeviceDisconnect", "Polaris:RestartDriver", "Polaris:StatusFetch", 
            "Polaris:SetMode", "Polaris:SetCompass", "Polaris:SetAlignment",
            "Polaris:ConfigFetch", "Polaris:ConfigUpdate", "Polaris:ConfigSave", "Polaris:ConfigRestore",
            "Polaris:MoveAxis", "Polaris:MoveMotor", 
            "Polaris:SpeedTestStart", "Polaris:SpeedTestStop", "Polaris:SpeedTestApprove",
            "Polaris:SyncRoll", "Polaris:SyncRemove",  
        ], req)  


@before(PreProcessRequest(maxdev, 'log_alpaca_actions'))
class action:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        actionName = await get_request_field('Action', req)
        raw_params = await get_request_field('Parameters', req)
        try:
            if isinstance(raw_params, dict):
                parameters = raw_params
            elif isinstance(raw_params, str) and raw_params.strip() == '':
                parameters = {}
            else:
                parameters = json.loads(raw_params)
        except Exception:
            raise HTTPBadRequest(title='Bad Action Request', description='Invalid Parameters format')

        if actionName == "Polaris:RestartDriver":
            await lifecycle.signal(LifecycleEvent.RESTART)
            resp.text = await PropertyResponse('RestartDriver ok', req)  

        elif actionName == "Polaris:ConfigFetch":
            fetched_params = Config.as_dict()
            # fetch live values from polaris where possible
            fetched_params['site_latitude'] = polaris.sitelatitude
            fetched_params['site_longitude'] = polaris.sitelongitude
            fetched_params['site_elevation'] = polaris.siteelevation

            # only return requested Config.names
            configNames = parameters.get('configNames')
            if isinstance(configNames, list) and len(configNames)>0:
                filtered_params = {k: fetched_params[k] for k in configNames if k in fetched_params}
            else:
                filtered_params = fetched_params

            resp.text = await PropertyResponse(filtered_params, req)
            return
        
        elif actionName == "Polaris:ConfigUpdate":
            # Apply changes to store in Config and make them live
            changed_params = Config.apply_changes(parameters)
            make_params_live(changed_params)
            resp.text = await PropertyResponse(changed_params, req)
            return

        elif actionName == "Polaris:ConfigSave":
            resp.text = await PropertyResponse(Config.save_pilot_overrides(), req)
            return

        elif actionName == "Polaris:ConfigRestore":
            # Restore Config from config.toml and make them live
            changed_params = Config.restore_base()
            make_params_live(changed_params)
            resp.text = await PropertyResponse(changed_params, req)
            return

        elif actionName == "Polaris:StatusFetch":       # (DO NOT USE) Replaced by WebSockets 
            resp.text = await PropertyResponse(polaris.getStatus(), req)
            return
        
        elif actionName == "Polaris:MoveAxis":
            logger.info(f'MoveAxis {parameters}')
            axis = parameters.get('axis', -1)
            rate = parameters.get('rate', 0)
            if axis in [0,1,2] and rate <10 and rate >-10:
                polaris._pid.set_alpha_axis_velocity(axis, rate)
            if axis in [3,4,5] and rate <10 and rate >-10:
                polaris._pid.set_delta_axis_velocity(axis-3, rate)
            resp.text = await PropertyResponse('MoveAxis ok', req)  
            return

        elif actionName == "Polaris:MoveMotor":
            logger.info(f'MoveAxis {parameters}')
            axis = parameters.get('axis', -1)
            rate = parameters.get('rate', 0)
            unit = parameters.get('unit', 'DPS')
            if axis in [0,1,2] and rate <10 and rate >-10:
                await polaris._motors[axis].set_motor_speed(rate, unit)
            resp.text = await PropertyResponse('MoveAxis ok', req)  
            return

        elif actionName == "Polaris:SpeedTestStart":
            logger.info(f'SpeedTestStart {parameters}')
            axis = parameters.get('axis', 0)
            testNames = parameters.get('testNames', -1)
            rates = polaris._cm.pendingTests(axis, testNames)
            lifecycle.create_task(polaris.moveaxis_speed_test(axis, rates), name="SpeedTest")
            resp.text = await PropertyResponse('SpeedTest ok', req)  
            return

        elif actionName == "Polaris:SpeedTestStop":
            logger.info(f'SpeedTestStop {parameters}')
            lifecycle.stop()
            polaris._cm.stopTests()
            # rates = polaris._cm.pendingTests(axis, testNames)
            resp.text = await PropertyResponse('SpeedTest ok', req)  
            return


        elif actionName == "Polaris:SpeedTestApproval":
            logger.info(f'SpeedTestApproval {parameters}')
            axis = parameters.get('axis', 0)
            testNames = parameters.get('testNames', -1)
            polaris._cm.toggleApproval(axis, testNames)
            resp.text = await PropertyResponse('TestApproval ok', req)  
            return

        elif actionName == "Polaris:bleEnableWifi":
            logger.info(f'BLE Enable Wifi {parameters}')
            lifecycle.create_task(polaris._ble.enableWifi(), name="bleEnableWifi")
            resp.text = await PropertyResponse('bleEnableWifi ok', req)  
            return

        elif actionName == "Polaris:bleSelectDevice":
            logger.info(f'BLE Select Device {parameters}')
            name = parameters.get('name', '')
            asyncio.create_task(polaris._ble.setSelectedDevice(name)) 
            resp.text = await PropertyResponse('bleSelectDevice ok', req)  
            return

        elif actionName == "Polaris:ConnectPolaris":
            logger.info(f'Device Connect {parameters}')
            lifecycle.create_task(polaris.run_connection_cycle(0), name="ConnectPolaris")
            resp.text = await PropertyResponse('ConnectPolaris ok', req)  
            return

        elif actionName == "Polaris:DisconnectPolaris":
            logger.info(f'Device Disconnect {parameters}')
            await polaris.attempt_polaris_disconnect()
            resp.text = await PropertyResponse('DisconnectPolaris ok', req)  
            return

        elif actionName == "Polaris:SetMode":
            logger.info(f'Polaris SetMode {parameters}')
            mode = int(parameters.get('mode', 8))
            await polaris.send_cmd_285_set_mode(mode)
            resp.text = await PropertyResponse('Polaris SetMode ok', req)  
            return

        elif actionName == "Polaris:SetCompass":
            logger.info(f'Polaris SetCompass {parameters}')
            compass = int(parameters.get('compass', 0))
            asyncio.create_task(polaris.skip_compass_alignment(compass)) 
            resp.text = await PropertyResponse('Polaris Set Compass ok', req)  
            return

        elif actionName == "Polaris:SetAlignment":
            logger.info(f'Polaris SetAlignment {parameters}')
            azimuth = int(parameters.get('azimuth', 0))
            altitude = int(parameters.get('altitude', 0))
            asyncio.create_task(polaris.skip_star_alignment(azimuth, altitude)) 
            resp.text = await PropertyResponse('Polaris Set Alignment ok', req)  
            return

        elif actionName == "Polaris:SyncRoll":
            logger.info(f'Polaris SyncRoll {parameters}')
            roll = int(parameters.get('roll', 0))
            await polaris.sync_to_roll(roll) 
            resp.text = await PropertyResponse('Polaris SyncRoll ok', req)  
            return

        elif actionName == "Polaris:SyncRemove":
            logger.info(f'Polaris SyncRemove {parameters}')
            timestamp = parameters.get('timestamp', '')
            polaris._sm.sync_remove(timestamp) 
            resp.text = await PropertyResponse('Polaris SyncRemove ok', req)  
            return

        else:
            resp.text = await MethodResponse(req, NotImplementedException(f'Unknown Action Name: {actionName}'))


def make_params_live(changed_params):
    # make changes live in polaris where possible
    for param in changed_params:
        if param == "log_level":
            update_log_level(Config.log_level)
        elif param == "site_latitude":
            polaris.sitelatitude = float(Config.site_latitude)
        elif param == "site_longitude":
            polaris.sitelongitude = float(Config.site_longitude)
        elif param == "site_elevation":
            polaris.siteelevation = Config.site_elevation
        elif param == "site_pressure":
            polaris.sitepressure = Config.site_pressure
        elif param == "max_accel_rate":        
            polaris._pid.set_Ka_array(Config.max_accel_rate)
        elif param == "max_slew_rate":
            polaris._pid.set_Kv_array(Config.max_slew_rate)

   

