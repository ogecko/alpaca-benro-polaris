# Telescope API Reference
[Telescope Members](#telescope-members) · [Common Members](#common-members)

The Telescope points and tracks the mount. It implements the ASCOM **ITelescopeV3** interface: see the [ASCOM Telescope interface](https://ascom-standards.org/newdocs/telescope.html) for the standard behaviour of each member. It's an Alt/Az mount (`alignmentmode` 0), and its right ascension and declination are topocentric JNow, the equinox of date (`equatorialsystem` 1). For J2000 coordinates, use the `Polaris:J2000Goto` and `Polaris:J2000Sync` [Device Actions](./alpaca-api.md#device-actions). The driver keeps every slew within what the Polaris can physically reach, where Altitude and Roll limit each other (see [Reachable Envelope](./kinematics.md#reachable-envelope)).

Each member is at `http://<driver address>:5555/api/v1/telescope/0/<member>`. GET requests read a property; PUT requests change it or run a method, with the fields listed as form data. Every request also needs `ClientID` and `ClientTransactionID`; see the [Alpaca API Reference](./alpaca-api.md) for examples.

This page is generated from the driver's code (`driver/telescope.py`) by `utility/docs/make_api_reference.py`: change the endpoint classes' docstrings rather than this page.

## Telescope Members

| Member | Method | Fields | Description |
|---|---|---|---|
| `abortslew` | PUT |  | Stop all movement: any slew, axis move and tracking. Fails while the mount is parked. |
| `alignmentmode` | GET |  | The mount's alignment mode. Always 0 (Alt/Az). |
| `altitude` | GET |  | The altitude the mount is pointing at, in degrees above the horizon. |
| `aperturearea` | GET |  | The telescope's aperture area in square metres, worked out from the focal length and focal ratio in Alpaca Pilot's settings. |
| `aperturediameter` | GET |  | The telescope's aperture diameter in metres, worked out from the focal length and focal ratio in Alpaca Pilot's settings. |
| `athome` | GET |  | Whether the mount is at its home position. |
| `atpark` | GET |  | Whether the mount is parked. Most movement commands fail while it is. |
| `axisrates` | GET | `Axis` | The range of rates `moveaxis` accepts for an `Axis` (0 to 2): 0.1 to 9 degrees per second. |
| `azimuth` | GET |  | The azimuth the mount is pointing at, in degrees east of north (0 to 360). |
| `canfindhome` | GET |  | Whether the mount can find its home position with `findhome`. Always true. |
| `canmoveaxis` | GET | `Axis` | Whether `moveaxis` can move an `Axis`. True for axis 0 (Azimuth), 1 (Altitude) and 2 (Roll). |
| `canpark` | GET |  | Whether the mount can be parked with `park`. Always true. |
| `canpulseguide` | GET |  | Whether the mount can be guided with `pulseguide`. Always true. |
| `cansetdeclinationrate` | GET |  | Whether `declinationrate` can be changed. Always false. |
| `cansetguiderates` | GET |  | Whether the guide rates can be changed. Always true. |
| `cansetpark` | GET |  | Whether the park position can be changed with `setpark`. Always true. |
| `cansetpierside` | GET |  | Whether `sideofpier` can be set to force a meridian flip. Always false. |
| `cansetrightascensionrate` | GET |  | Whether `rightascensionrate` can be changed. Always false. |
| `cansettracking` | GET |  | Whether tracking can be turned on and off with `tracking`. Always true. |
| `canslew` | GET |  | Whether the mount can slew to RA/Dec coordinates with `slewtocoordinates`. Always true. |
| `canslewaltaz` | GET |  | Whether the mount can slew to Alt/Az coordinates with `slewtoaltaz`. Always true. |
| `canslewaltazasync` | GET |  | Whether the mount can slew to Alt/Az coordinates with `slewtoaltazasync`. Always true. |
| `canslewasync` | GET |  | Whether the mount can slew to RA/Dec coordinates with `slewtocoordinatesasync`. Always true. |
| `cansync` | GET |  | Whether the mount can be synced to RA/Dec coordinates with `synctocoordinates`. Always true. |
| `cansyncaltaz` | GET |  | Whether the mount can be synced to Alt/Az coordinates with `synctoaltaz`. Always true. |
| `canunpark` | GET |  | Whether the mount can be unparked with `unpark`. Always true. |
| `declination` | GET |  | The declination the mount is pointing at, in degrees (topocentric JNow). |
| `declinationrate` | GET / PUT |  | The declination tracking rate offset, in arcseconds per second. Always 0: it can't be changed. |
| `destinationsideofpier` | GET | `RightAscension`, `Declination` | The side of pier the mount would be on after slewing to `RightAscension` (hours, 0 to 24) and `Declination` (degrees, -90 to +90). Always 0, as an Alt/Az mount has no meridian flip. |
| `dispose` | PUT |  | Release the driver's resources. *(Not implemented.)* |
| `doesrefraction` | GET / PUT | `DoesRefraction` | Whether the driver corrects coordinates for atmospheric refraction. Set with `DoesRefraction`. On by default. |
| `equatorialsystem` | GET |  | The coordinate system the driver's RA/Dec use. Always 1 (topocentric JNow, the equinox of date). |
| `findhome` | PUT |  | Move the mount to its home position, with all three motors at 0. Stops tracking first. Fails while the mount is parked. |
| `focallength` | GET |  | The telescope's focal length in metres, from the focal length in Alpaca Pilot's settings. |
| `guideratedeclination` | GET / PUT | `GuideRateDeclination` | The rate `pulseguide` moves the mount north or south, in degrees per second. Set with `GuideRateDeclination` (0 to 2). Starts at the guide rate in Alpaca Pilot's settings. |
| `guideraterightascension` | GET / PUT | `GuideRateRightAscension` | The rate `pulseguide` moves the mount east or west, in degrees per second. Set with `GuideRateRightAscension` (0 to 2). Starts at the guide rate in Alpaca Pilot's settings. |
| `ispulseguiding` | GET |  | Whether a `pulseguide` move is under way. |
| `moveaxis` | PUT | `Axis`, `Rate` | Move one `Axis` at a steady `Rate` in degrees per second: axis 0 is Azimuth, 1 Altitude and 2 Roll. The rate is 0.1 to 9, negative to reverse, or 0 to stop. Ends any sync guiding. Fails while parked, or while a goto is under way. |
| `park` | PUT |  | Move the mount to its park position, set with `setpark`, and stop tracking. |
| `pulseguide` | PUT | `Direction`, `Duration` | Nudge the mount at the guide rate in a `Direction` (0 North, 1 South, 2 East, 3 West) for a `Duration` in milliseconds (1 to 10000). Fails unless the mount is tracking, or while it's parked or slewing. See [Pulse Guiding](./guiding-pulse.md). |
| `rightascension` | GET |  | The right ascension the mount is pointing at, in hours (topocentric JNow). |
| `rightascensionrate` | GET / PUT |  | The right ascension tracking rate offset, in seconds per sidereal second. Always 0: it can't be changed. |
| `setpark` | PUT |  | Make the mount's current position its park position. Fails while slewing. |
| `sideofpier` | GET / PUT |  | The mount's pointing state. An Alt/Az mount has no meridian flip, so this is -1 (unknown) and can't be set. |
| `siderealtime` | GET |  | The local apparent sidereal time at the site, in hours. |
| `siteelevation` | GET / PUT | `SiteElevation` | The site's elevation in metres. Set with `SiteElevation` (0 to 10000). Usually set in Alpaca Pilot. |
| `sitelatitude` | GET / PUT | `SiteLatitude` | The site's latitude in degrees, north positive. Set with `SiteLatitude` (-90 to 90). Usually set in Alpaca Pilot. |
| `sitelongitude` | GET / PUT | `SiteLongitude` | The site's longitude in degrees, east positive. Set with `SiteLongitude` (-180 to 180). Usually set in Alpaca Pilot. |
| `slewing` | GET |  | Whether the mount is slewing. |
| `slewsettletime` | GET / PUT | `SlewSettleTime` | Extra time to wait after a slew before reporting it finished, in seconds. Set with `SlewSettleTime` (0 to 200). Defaults to 0. |
| `slewtoaltaz` | PUT | `Azimuth`, `Altitude` | Slew to an `Azimuth` (0 to 360) and `Altitude` (-8 to 90) in degrees, returning when the slew finishes. Fails while parked or slewing. |
| `slewtoaltazasync` | PUT | `Azimuth`, `Altitude` | Slew to an `Azimuth` (0 to 360) and `Altitude` (-8 to 90) in degrees, returning straight away. Watch `slewing` to see when it finishes. Fails while parked. |
| `slewtocoordinates` | PUT | `RightAscension`, `Declination` | Slew to a `RightAscension` in hours (0 to 24) and `Declination` in degrees (-90 to +90), topocentric JNow, returning when the slew finishes. Fails while parked or slewing. |
| `slewtocoordinatesasync` | PUT | `RightAscension`, `Declination` | Slew to a `RightAscension` in hours (0 to 24) and `Declination` in degrees (-90 to +90), topocentric JNow, returning straight away. Watch `slewing` to see when it finishes. Fails while parked. |
| `slewtotarget` | PUT |  | Slew to `targetrightascension` and `targetdeclination`, returning when the slew finishes. Fails while parked or slewing. |
| `slewtotargetasync` | PUT |  | Slew to `targetrightascension` and `targetdeclination`, returning straight away. Watch `slewing` to see when it finishes. Fails while parked. |
| `synctoaltaz` | PUT | `Azimuth`, `Altitude` | Tell the driver the mount is really pointing at an `Azimuth` (0 to 360) and `Altitude` (-90 to +90) in degrees, for example a landmark. |
| `synctocoordinates` | PUT | `RightAscension`, `Declination` | Tell the driver the mount is really pointing at a `RightAscension` in hours (0 to 24) and `Declination` in degrees (-90 to +90), for example from a plate solve. Adds a point to the Multi-Point Alignment model when it's on, or else corrects the single-point alignment. Fails while parked. |
| `synctotarget` | PUT |  | Sync to `targetrightascension` and `targetdeclination`, the same as `synctocoordinates`. Fails while parked. |
| `targetdeclination` | GET / PUT | `TargetDeclination` | The declination for `slewtotarget` and `synctotarget`, in degrees. Set with `TargetDeclination` (-90 to +90). Reading it fails until it's set. |
| `targetrightascension` | GET / PUT | `TargetRightAscension` | The right ascension for `slewtotarget` and `synctotarget`, in hours. Set with `TargetRightAscension` (0 to 24). Reading it fails until it's set. |
| `tracking` | GET / PUT | `Tracking` | Whether the mount is tracking the sky. Set `Tracking` to true or false to start or stop tracking. |
| `trackingrate` | GET / PUT | `TrackingRate` | The tracking rate in use. Set with `TrackingRate`: 0 Sidereal, 1 Lunar, 2 Solar or 3 King. |
| `trackingrates` | GET |  | The tracking rates the mount supports: 0 Sidereal, 1 Lunar, 2 Solar and 3 King. |
| `unpark` | PUT |  | Unpark the mount, so it can move again. |
| `utcdate` | GET / PUT |  | The driver's UTC date and time. It can't be set: the driver uses its computer's clock. |

## Common Members

The members every ASCOM device has.

| Member | Method | Fields | Description |
|---|---|---|---|
| `action` | PUT | `Action`, `Parameters` | Run a Device Action, named by `Action`, with its `Parameters` as a JSON string. See [Device Actions](./alpaca-api.md#device-actions). |
| `commandblind` | PUT |  | Send a raw command to the mount without waiting for a reply. *(Not implemented.)* |
| `commandbool` | PUT |  | Send a raw command to the mount and return a true/false reply. *(Not implemented.)* |
| `commandstring` | PUT |  | Send a raw command to the mount and return its text reply. *(Not implemented.)* |
| `connected` | GET / PUT | `Connected` | Whether this client is connected to the driver. Set `Connected` to true or false to connect or disconnect. The driver tracks each `ClientID` separately. |
| `description` | GET |  | A description of the device, the Benro Polaris. |
| `driverinfo` | GET |  | A description of the driver. |
| `driverversion` | GET |  | The driver's version number. |
| `interfaceversion` | GET |  | The version of the ASCOM Telescope interface the driver implements, 3 for ITelescopeV3. |
| `name` | GET |  | The device's short name. |
| `supportedactions` | GET |  | The Device Actions the driver supports, the `Polaris:` actions. See [Device Actions](./alpaca-api.md#device-actions). |
