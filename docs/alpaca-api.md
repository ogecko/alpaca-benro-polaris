# Alpaca API Reference
[Discovery](#discovery) · [Management](#management) · [Telescope](#telescope) · [Rotator](#rotator) · [Device Actions](#device-actions)

The Alpaca Driver presents the Benro Polaris to astronomy applications as two standard ASCOM Alpaca devices, a **Telescope** and a **Rotator**, together with a set of **Device Actions** for features that go beyond the ASCOM standard. Applications like NINA, PHD2, Stellarium and CCDciel make these calls for you. This page is for anyone who wants to script the mount directly, or understand what their applications are doing.

All requests go to the driver's Alpaca REST API on port `5555` (the `alpaca_restapi_port` setting), at `http://<driver address>:5555/api/v1/<device>/0/<member>`. The examples below use `ap.local` as the driver address; use the IP address of the computer running the driver if `ap.local` doesn't resolve on your network (see [Launching the Alpaca Pilot Application](./pilot.md#launching-alpaca-pilot)). Each request includes a `ClientID` and `ClientTransactionID`, and the driver must be connected to the Polaris for most calls to succeed.

## Discovery

Applications find the Alpaca Driver using ASCOM Alpaca discovery. They broadcast the message `alpacadiscovery1` on UDP port `32227` (the `alpaca_discovery_port` setting), and the driver replies with the port of its REST API, for example `{"AlpacaPort": 5555}`. This is how NINA and other Alpaca applications list the driver's devices without you entering its address. Discovery only works within your local network, so if an application can't find the driver, enter the driver's IP address and port `5555` instead. See the [ASCOM Alpaca API reference](https://ascom-standards.org/api/) for the discovery protocol.

## Management

The Management API describes the driver and the devices it offers. List the configured devices:

```
curl "http://ap.local:5555/management/v1/configureddevices?ClientID=1&ClientTransactionID=1"
```

The response lists each device with its type and device number, the `0` in each device's URL:

```json
{"Value": [
  {"DeviceName": "Alpaca Benro Polaris Telescope", "DeviceType": "Telescope", "DeviceNumber": 0, "UniqueID": "..."},
  {"DeviceName": "Alpaca Benro Polaris Rotator", "DeviceType": "Rotator", "DeviceNumber": 0, "UniqueID": "..."}
], "ClientTransactionID": 1, "ServerTransactionID": 1, "ErrorNumber": 0, "ErrorMessage": ""}
```

The Rotator is only listed when **Alpaca Rotator** is enabled under **Advanced Control Features** in Alpaca Pilot's Settings. `/management/v1/description` returns the driver's name, version and location, and `/management/apiversions` the Alpaca API versions it supports.

Every device also has the members common to all ASCOM devices, such as `connected`, `name`, `description`, `driverinfo`, `driverversion` and `supportedactions`. For example, `GET /api/v1/telescope/0/supportedactions` lists all of the Telescope's Device Actions.

## Telescope

The Telescope device implements the ASCOM **ITelescopeV3** interface. See the [ASCOM Telescope interface](https://ascom-standards.org/newdocs/telescope.html) for what each property and method does, and the [ASCOM Alpaca API reference](https://ascom-standards.org/api/) for the REST calls. Meridian flips are not supported, as the Polaris is an Alt/Az mount.

Read the Right Ascension the mount is pointing at, in hours:

```
curl "http://ap.local:5555/api/v1/telescope/0/rightascension?ClientID=1&ClientTransactionID=1"
```

The response gives the value, along with any error:

```json
{"Value": 5.5881, "ClientTransactionID": 1, "ServerTransactionID": 42, "ErrorNumber": 0, "ErrorMessage": ""}
```

Slew to the Orion Nebula (Right Ascension in hours, Declination in degrees):

```
curl -X PUT http://ap.local:5555/api/v1/telescope/0/slewtocoordinatesasync \
     -d "RightAscension=5.5881&Declination=-5.391&ClientID=1&ClientTransactionID=2"
```

## Rotator

The Rotator device implements the ASCOM **IRotatorV3** interface. See the [ASCOM Rotator interface](https://ascom-standards.org/newdocs/rotator.html) and the [ASCOM Alpaca API reference](https://ascom-standards.org/api/). Rotating the camera keeps the mount pointing at the same target. The Rotator's `Position` is the Position Angle of the camera on the sky, and its `MechanicalPosition` is the Roll Angle of the camera relative to the horizon (see [Roll Angle vs. Position Angle](./control.md#roll-angle-vs-position-angle)).

Read the current Position Angle, in degrees:

```
curl "http://ap.local:5555/api/v1/rotator/0/position?ClientID=1&ClientTransactionID=3"
```

Rotate the camera to a Position Angle of 90°:

```
curl -X PUT http://ap.local:5555/api/v1/rotator/0/moveabsolute \
     -d "Position=90&ClientID=1&ClientTransactionID=4"
```

## Device Actions

Device Actions are the ASCOM standard's way for a driver to offer features that the standard interfaces don't cover. The Alpaca Driver's Device Actions belong to the Telescope device and are named `Polaris:<action>`. Alpaca Pilot uses many of them internally; the ones documented here are those that are useful in your own sequences and scripts.

Three approaches you can use Device Actions, include:

1. From NINA's [Advanced Sequencer](./nina.md#advanced-sequence), install the **Device Actions and Commands** plug-in, then add a **Utility > Device Action** instruction, set the Device to `Telescope`, and choose the Action and its Parameters as shown in the tables below. 
2. From CCDciel, run one of the Alpaca Driver's scripts as a step of a plan, see [Scripting](./ccdciel.md#scripting) in the CCDciel guide.
3. Call them directly through the REST API, with the Parameters as a JSON object:

     ```
     curl -X PUT http://ap.local:5555/api/v1/telescope/0/action \
          -d "Action=Polaris:PanoSlew&ClientID=1&ClientTransactionID=5" \
          --data-urlencode 'Parameters={"panel": 1}'
     ```

### Polaris:PanoGrid
Set up a panorama or mosaic grid, the same settings as the PanoGrid page in Alpaca Pilot. Any of these settings can be given, the rest keep their current values: `cols`, `rows` (the grid size), `hstep`, `vstep` (degrees between panel centres), `first` (corner of panel 1: 0 Top Left, 1 Top Right, 2 Bottom Left, 3 Bottom Right), `order` (0 Row-Major, 1 Column-Major, 2 Serpentine), `track` (0 Landscape - Untracked, 1 Sky - Horizon-Locked, 2 Sky - Celestial, 3 Sky - Milky Way), `anchor` (what sits at the reference position: 0 the whole mosaic's centre, n panel n), `ref` (reference frame: 0 Az/Alt/Roll, 1 RA/Dec/PA, 2 Galactic, 3 Motor Position) and `r1`, `r2`, `r3` (the reference position in that frame, RA in hours). Use **Polaris:ConfigSave** to keep them for the next session.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:PanoGrid` |  `{"cols": 5, "rows": 3, "hstep": 2.0, "vstep": 1.4, "first": 0, "order": 2, "track": 2}` |
| **Utility > Device Action** | `Telescope` |  `Polaris:PanoGrid` |  `{"anchor": 0, "ref": 1, "r1": 5.59, "r2": -5.39, "r3": 0}` |

### Polaris:PanoSlew
Slew to a panel of the grid set by **Polaris:PanoGrid**, rolling and tracking as its `track` setting says. `panel` is the panel number (1 to cols x rows); leave it out to go to the next panel (after the last it wraps round to panel 1), or use -1 to return to the current one. It waits for the slew to finish unless `"isasync": true` is given. In an advanced sequence a loop of **Polaris:PanoSlew** `{}` followed by your exposures captures the whole grid.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:PanoSlew` |  `{"panel": 1}` |
| **Utility > Device Action** | `Telescope` |  `Polaris:PanoSlew` |  `{}` |

### Polaris:SlewAbsolute
Slew to a position given in any one co-ordinate system, including Roll and Position Angle, which the standard ASCOM slews can't set: `az`, `alt`, `roll` (topocentric), `ra` (hours), `dec`, `pa` (equatorial), `l`, `b`, `gpa` (galactic), or `m1`, `m2`, `m3` (motor angles). Values are decimal degrees, or strings such as `"-05:23:28"`. Axes left out keep their current value. Motor angles are the M1/M2/M3 shown in Alpaca Pilot's Motor Speed & Position panel; the motors are driven straight to them, so M1 and M3 always end the same way round, and the cables in the same state. They must be within the motor limits and can't be mixed with the other keys. It waits for the slew to finish unless `"isasync": true` is given. Needs Advanced Goto enabled.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:SlewAbsolute` |  `{"az": 180, "alt": 81, "roll": 0}` |
| **Utility > Device Action** | `Telescope` |  `Polaris:SlewAbsolute` |  `{"pa": 90}` |
| **Utility > Device Action** | `Telescope` |  `Polaris:SlewAbsolute` |  `{"m1": 0, "m2": -30, "m3": 0}` |

### Polaris:SlewRelative
As **Polaris:SlewAbsolute**, but each value is added to the current position: for example to step the framing, or turn the camera. Motor angles add to the current motor angles.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:SlewRelative` |  `{"ra": 0.1, "dec": -1.5}` |
| **Utility > Device Action** | `Telescope` |  `Polaris:SlewRelative` |  `{"roll": 90}` |

### Polaris:AbortSlew
Stop any goto, slew or axis movement and stop tracking, the same as the Stop button in Alpaca Pilot.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:AbortSlew` |  `{}` |

### Polaris:MoveAxis
Move continuously along one axis at `rate` degrees per second (negative for the other direction) until it is called again with `"rate": 0`. `axis` is 0 Azimuth, 1 Altitude, 2 Roll, 3 RA, 4 Dec, 5 Position Angle, 6 Galactic longitude, 7 Galactic latitude, 8 Galactic PA. The mount combines the motors to move along that axis only, as the Alpaca Pilot joysticks do. Needs Advanced Slewing enabled.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:MoveAxis` |  `{"axis": 2, "rate": 3}` |
| **Utility > Device Action** | `Telescope` |  `Polaris:MoveAxis` |  `{"axis": 2, "rate": 0}` |

### Polaris:MoveMotor
Run one motor directly at `rate` degrees per second (between -9 and +9), with no co-ordination or pointing control, until it is called again with `"rate": 0`. `axis` is 0 M1, 1 M2, 2 M3. Meant for testing and for unwinding cables: the motor keeps running until stopped, or until it reaches its motor limit, where the driver stops all motors.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:MoveMotor` |  `{"axis": 0, "rate": -5}` |
| **Utility > Device Action** | `Telescope` |  `Polaris:MoveMotor` |  `{"axis": 0, "rate": 0}` |

### Polaris:ResetAxes
Command the Polaris to reset all three axes, which drives each motor to its zero. This replicates the double-tap gesture on each joystick in the Benro Polaris App. After the Polaris is switched on, the first reset also re-takes each motor's zero from its position sensor, which only knows the angle within one turn. If the head was more than half a turn from its home position when the Polaris was switched on (for example cables wound by a long satellite pass), unwind it by hand first: otherwise the reset can turn it a further turn the same way and the zero ends a whole turn out.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:ResetAxes` |  `{}` |

### Polaris:ReplayMark
Write a marker line (`REPLAYLOG`) with the given parameters into the Alpaca Driver's log, whatever the log settings. Useful to mark where something happened in a sequence (a new target, a filter change, the start of a test) so it can be found later in the log, on the same timeline as the driver's own records.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:ReplayMark` |  `{"note": "NGC 104 start"}` |

### Polaris:TrackOrbital
Fetch the orbital parameters of an object, slew to its co-ordinates and start non-sidereal tracking. This Device Action can be used to slew to the Moon, Sun, Satellites, Comets etc. The Parameters field should be in JSON format defining "name" and "category" of the object, where category 3: 'Star', 4: 'Planet', 5: 'Moon', 6: 'Satellite', 7: 'Commet', 8: 'Asteroid', 9: 'Landmark', 10: 'Custom'. For example to track a Solar Eclipse, Lunar Eclipse or the International Space Station use the following settings.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:TrackOrbital` |  `{"name": "Sun", "category":3}` |
| **Utility > Device Action** | `Telescope` |  `Polaris:TrackOrbital` |  `{"name": "Moon", "category":5}` |
| **Utility > Device Action** | `Telescope` |  `Polaris:TrackOrbital` |  `{"name": "25544", "category":6}` |

### Polaris:ConfigUpdate
Update the Alpaca Driver configuration setting to the defined values. Any property defined in config.toml can be modified with this action. The Parameters field should be in JSON format defining a list of properties and values to change. Separate multiple property:values with a comma. For example to (a) enable multi-point alignment (b) reduce the goto tollerance to 15 arc-min, (c) to alter the park position and (d) to alter the ASCOM focal length; use the following.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:ConfigUpdate` |  `{"advanced_alignment": true}` |
| **Utility > Device Action** | `Telescope` |  `Polaris:ConfigUpdate` |  `{"pid_Kc": 15}` |
| **Utility > Device Action** | `Telescope` |  `Polaris:ConfigUpdate` |  `{"m3_park": 90, "m2_park":-45}` |
| **Utility > Device Action** | `Telescope` |  `Polaris:ConfigUpdate` |  `{"focal_length": 100}` |

Note that the **Polaris:ConfigUpdate** action returns a value indicating what has been changed. Nina doesnt understand this reponse and marks the instruction execution return as an error. You can safely ignore this in the advanced sequence and mark the instruction as **On Error** `Continue`

### Polaris:ConfigSave
Save any modified Alpaca Driver settings to the file `config.pilot.json` in the data directory.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:ConfigSave` |  `{}` |

### Polaris:ConfigRestore
Restore all Alpaca Driver settings back to the defaults from `config.toml`.

| **Instruction** | **Device** | Action | Parameters |
| --- | --- | --- | --- |
| **Utility > Device Action** | `Telescope` |  `Polaris:ConfigRestore` |  `{}` |
