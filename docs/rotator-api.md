# Rotator API Reference
[Rotator Members](#rotator-members) · [Common Members](#common-members)

The Rotator rotates the camera around the direction it's pointing, while the mount stays on target. It implements the ASCOM **IRotatorV3** interface: see the [ASCOM Rotator interface](https://ascom-standards.org/newdocs/rotator.html) for the standard behaviour of each member. Its `position` is the camera's Position Angle on the sky, and its `mechanicalposition` is the camera's Roll Angle relative to the horizon (see [Roll Angle vs Position Angle](./control.md#roll-angle-vs-position-angle)). So `moveabsolute` to 0 turns the top of the frame to celestial north, not level with the horizon: use `movemechanical` to set the Roll Angle.

Each member is at `http://<driver address>:5555/api/v1/rotator/0/<member>`. GET requests read a property; PUT requests change it or run a method, with the fields listed as form data. Every request also needs `ClientID` and `ClientTransactionID`; see the [Alpaca API Reference](./alpaca-api.md) for examples.

This page is generated from the driver's code (`driver/rotator.py`) by `utility/docs/make_api_reference.py`: change the endpoint classes' docstrings rather than this page.

## Rotator Members

| Member | Method | Fields | Description |
|---|---|---|---|
| `canreverse` | GET |  | Whether the Rotator supports reversing its direction: always true. |
| `halt` | PUT |  | Stop rotating. This stops the whole mount, including any slew and tracking, the same as the Telescope's `abortslew`. Fails while the mount is parked. |
| `ismoving` | GET |  | Whether the Rotator is rotating the camera. |
| `mechanicalposition` | GET |  | The camera's Roll Angle, in degrees: its angle relative to the horizon. |
| `move` | PUT | `Position` | Rotate the camera by `Position` degrees (-540 to 540), relative to its current Position Angle. Needs Alpaca Rotator to be on, and ends any sync guiding. |
| `moveabsolute` | PUT | `Position` | Rotate the camera to a Position Angle, given as `Position` in degrees (-180 to 360). Keeps the mount pointing at the same target. Needs Alpaca Rotator to be on, and ends any sync guiding. |
| `movemechanical` | PUT | `Position` | Rotate the camera to a Roll Angle, given as `Position` in degrees (-180 to 360). Keeps the mount pointing at the same target. Needs Alpaca Rotator to be on in Alpaca Pilot's settings, and ends any sync guiding. |
| `position` | GET |  | The camera's Position Angle on the sky, in degrees: its angle relative to celestial north. |
| `reverse` | GET / PUT | `Reverse` | Whether the Rotator's direction is reversed. Set with `Reverse`. The value is stored and reported, but the driver doesn't currently act on it. |
| `stepsize` | GET |  | The smallest rotation step, in degrees: one arc second (1/3600). |
| `sync` | PUT | `Position` | Tell the driver the camera's true Position Angle, given as `Position` in degrees (-180 to 360), for example from a plate solve. Adds a roll sync point to the Multi-Point Alignment model, so has no effect unless Multi-Point Alignment is on. |
| `targetposition` | GET |  | The Position Angle the Rotator is moving to, in degrees. |

## Common Members

The members every ASCOM device has.

| Member | Method | Fields | Description |
|---|---|---|---|
| `action` | PUT |  | Run a Device Action. The Rotator has none: the Alpaca Driver's Device Actions are on the Telescope. *(Not implemented.)* |
| `commandblind` | PUT |  | Send a raw command to the device. Not implemented. |
| `commandbool` | PUT |  | Send a raw command and return a boolean. Not implemented. |
| `commandstring` | PUT |  | Send a raw command and return a string. Not implemented. |
| `connected` | GET / PUT | `Connected` | Whether this client is connected to the Rotator. Set `Connected` to true or false to connect or disconnect; each `ClientID` connects separately. |
| `description` | GET |  | A description of the Rotator device. |
| `driverinfo` | GET |  | Information about the driver, including the interface it implements (IRotatorV3). |
| `driverversion` | GET |  | The Alpaca Driver's version. |
| `interfaceversion` | GET |  | The ASCOM Rotator interface version the driver implements: 3. |
| `name` | GET |  | The Rotator's name, as shown in applications: Alpaca Benro Polaris Rotator. |
| `supportedactions` | GET |  | The Device Actions the Rotator supports: none (an empty list). |
