
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
from logging import Logger
from shr import PropertyResponse, MethodResponse, PreProcessRequest, get_request_field, to_bool
from exceptions import *        # Nothing but exception classes
from polaris import Polaris
import asyncio

logger: Logger = None

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
    Name = 'Benro Polaris'
    Version = 'v0.3'
    Description = 'ASCOM Alpaca Telescope Driver'
    DeviceType = 'Telescope'
    DeviceID = '3ee8e486-6421-432c-9a66-cf240e298bb9' # https://guidgenerator.com/online-guid-generator.aspx
    Info = 'Limited ASCOM Alpaca driver for the\nBenro Polaris Tripod Head & Astro.\nImplements ASCOM  ITelescopeV3.'
    MaxDeviceNumber = maxdev
    InterfaceVersion = 3

# ----------------------------------------------------------------------
# Create an instance of the Polaris Class to simulate an ASCOM telescope
# ----------------------------------------------------------------------
polaris = None
# At app init not import :-)
def start_polaris(logger: Logger): 
    global polaris
    polaris = Polaris(logger)
    
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

@before(PreProcessRequest(maxdev))
class dispose:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())

@before(PreProcessRequest(maxdev))
class findhome:
    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())

@before(PreProcessRequest(maxdev))
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
        if rightascension < 0 or rightascension > 24:
            resp.text = await MethodResponse(req, InvalidValueException(f'RightAscension {rightascensionstr} must be between 0 and 24.'))
            return
        declinationstr = await get_request_field('Declination', req)      # Raises 400 bad request if missing
        try:
            declination = float(declinationstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} not a valid number.'))
            return
        if declination < -90 or declination > +90:
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} must be between -90 and +90.'))
            return
        resp.text = await PropertyResponse(0, req)

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

@before(PreProcessRequest(maxdev))
class description:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(TelescopeMetadata.Description, req)

@before(PreProcessRequest(maxdev))
class driverinfo:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(TelescopeMetadata.Info, req)

@before(PreProcessRequest(maxdev))
class interfaceversion:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(TelescopeMetadata.InterfaceVersion, req)

@before(PreProcessRequest(maxdev))
class driverversion():
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(TelescopeMetadata.Version, req)

@before(PreProcessRequest(maxdev))
class name():
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse(TelescopeMetadata.Name, req)

@before(PreProcessRequest(maxdev))
class supportedactions:
    async def on_get(self, req: Request, resp: Response, devnum: int):
        resp.text = await PropertyResponse([], req)  # Not PropertyNotImplemented

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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
        polaris.doesrefraction = to_bool(doesrefractionstr)                       # Same here

        try:
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Doesrefraction failed', ex))

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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
        if siteelevation < 0 or siteelevation > 10000:
            resp.text = await MethodResponse(req, InvalidValueException(f'SiteElevation {siteelevationstr} must be between 0 and 10000.'))
            return
        try:
            polaris.siteelevation = siteelevation
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.Siteelevation failed', ex))

@before(PreProcessRequest(maxdev))
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
        if sitelatitude < -90 or sitelatitude > 90:
            resp.text = await MethodResponse(req, InvalidValueException(f'SiteLatitude {sitelatitudestr} must be between -90 and 90.'))
            return
        try:
            polaris.sitelatitude = sitelatitude
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.Sitelatitude failed', ex))

@before(PreProcessRequest(maxdev))
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
        if sitelongitude < -180 or sitelongitude > 180:
            resp.text = await MethodResponse(req, InvalidValueException(f'SiteLongitude {sitelongitudestr} must be between -180 and 180.'))
            return
        try:
            polaris.sitelongitude = sitelongitude
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.Sitelongitude failed', ex))

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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
        if targetdeclination < -90 or targetdeclination > +90:
            resp.text = await MethodResponse(req, InvalidValueException(f'TargetDeclination {targetdeclinationstr} must be between -90 and +90.'))
            return
        try:
            polaris.targetdeclination = targetdeclination
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.targetdeclination failed', ex))

@before(PreProcessRequest(maxdev))
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
        if targetrightascension < 0 or targetrightascension > 24:
            resp.text = await MethodResponse(req, InvalidValueException(f'TargetRightAscension {targetrightascensionstr} must be between 0 and 24.'))
            return
        try:
            polaris.targetrightascension = targetrightascension
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req, DriverException(0x500, 'Telescope.targetrightascension failed', ex))

@before(PreProcessRequest(maxdev))
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
            slewing = polaris.slewing
            oldtracking = polaris.tracking
            polaris.tracking = tracking
            # only send message if requested state differs and not slewing
            if tracking != oldtracking and not slewing:
                await polaris.send_cmd_change_tracking_state(tracking)                       # Same here

            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Tracking failed', ex))

@before(PreProcessRequest(maxdev))
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
        resp.text = await PropertyResponse(None, req, NotImplementedException())

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
class abortslew:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        if polaris.atpark:
            resp.text = await PropertyResponse(None, req, InvalidOperationException('Cannot abort slew while parked'))
            return
        try:
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Abortslew failed', ex))

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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
        if (rate != 0 and abs(rate) < polaris.axisrates[0]['Minimum']) or abs(rate) > polaris.axisrates[0]['Maximum']:
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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
        if azimuth < 0 or azimuth > +360:
            resp.text = await MethodResponse(req, InvalidValueException(f'Azimuth {azimuthstr} must be between 0 and 360.'))
            return
        altitudestr = await get_request_field('Altitude', req)      # Raises 400 bad request if missing
        try:
            altitude = float(altitudestr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Altitude {altitudestr} not a valid number.'))
            return
        if altitude < 0 or altitude > +90:
            resp.text = await MethodResponse(req, InvalidValueException(f'Altitude {altitudestr} must be between 0 and 90.'))
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

@before(PreProcessRequest(maxdev))
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
        if azimuth < 0 or azimuth > +360:
            resp.text = await MethodResponse(req, InvalidValueException(f'Azimuth {azimuthstr} must be between 0 and 360.'))
            return
        altitudestr = await get_request_field('Altitude', req)      # Raises 400 bad request if missing
        try:
            altitude = float(altitudestr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Altitude {altitudestr} not a valid number.'))
            return
        if altitude < 0 or altitude > +90:
            resp.text = await MethodResponse(req, InvalidValueException(f'Altitude {altitudestr} must be between 0 and 90.'))
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

@before(PreProcessRequest(maxdev))
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
        if rightascension < 0 or rightascension > 24:
            resp.text = await MethodResponse(req, InvalidValueException(f'RightAscension {rightascensionstr} must be between 0 and 24.'))
            return
        declinationstr = await get_request_field('Declination', req)      # Raises 400 bad request if missing
        try:
            declination = float(declinationstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} not a valid number.'))
            return
        if declination < -90 or declination > +90:
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

@before(PreProcessRequest(maxdev))
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
        if rightascension < 0 or rightascension > 24:
            resp.text = await MethodResponse(req, InvalidValueException(f'RightAscension {rightascensionstr} must be between 0 and 24.'))
            return
        declinationstr = await get_request_field('Declination', req)      # Raises 400 bad request if missing
        try:
            declination = float(declinationstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} not a valid number.'))
            return
        if declination < -90 or declination > +90:
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
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

@before(PreProcessRequest(maxdev))
class synctoaltaz:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        resp.text = await MethodResponse(req, NotImplementedException())
        return
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        azimuthstr = await get_request_field('Azimuth', req)      # Raises 400 bad request if missing
        try:
            azimuth = int(azimuthstr)
        except:
            resp.text = await MethodResponse(req,
                            InvalidValueException(f'Azimuth {azimuthstr} not a valid number.'))
            return
        ### RANGE CHECK AS NEEDED ###       # Raise Alpaca InvalidValueException with details!
        altitudestr = await get_request_field('Altitude', req)      # Raises 400 bad request if missing
        try:
            altitude = int(altitudestr)
        except:
            resp.text = await MethodResponse(req,
                            InvalidValueException(f'Altitude {altitudestr} not a valid number.'))
            return
        ### RANGE CHECK AS NEEDED ###       # Raise Alpaca InvalidValueException with details!
        try:
            # -----------------------------
            ### DEVICE OPERATION(PARAM) ###
            # -----------------------------
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Synctoaltaz failed', ex))

@before(PreProcessRequest(maxdev))
class synctocoordinates:

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
        if rightascension < 0 or rightascension > 24:
            resp.text = await MethodResponse(req, InvalidValueException(f'RightAscension {rightascensionstr} must be between 0 and 24.'))
            return
        declinationstr = await get_request_field('Declination', req)      # Raises 400 bad request if missing
        try:
            declination = float(declinationstr)
        except:
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} not a valid number.'))
            return
        if declination < -90 or declination > +90:
            resp.text = await MethodResponse(req, InvalidValueException(f'Declination {declinationstr} must be between -90 and +90.'))
            return
        try:
            polaris.radec_sync_ascom(rightascension, declination)
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Synctocoordinates failed', ex))

@before(PreProcessRequest(maxdev))
class synctotarget:

    async def on_put(self, req: Request, resp: Response, devnum: int):
        if not polaris.connected:
            resp.text = await PropertyResponse(None, req, NotConnectedException())
            return
        try:
            polaris.radec_sync_ascom(polaris.targetrightascension, polaris.targetdeclination)
            resp.text = await MethodResponse(req)
        except Exception as ex:
            resp.text = await MethodResponse(req,
                            DriverException(0x500, 'Telescope.Synctotarget failed', ex))

@before(PreProcessRequest(maxdev))
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

