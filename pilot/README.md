# Alpaca Benro Polaris Pilot (Position Control Reimagined)

Alpaca Pilot is a modern control interface for astronomical mounts, designed to streamline and reimagine the way users interact with Alpaca-compatible devices. With intuitive dashboards, responsive controls, and real-time telemetry visualization, Alpaca Pilot empowers observers to manage slewing, rotating, targeting, tracking, guiding, and alignment with confidence and clarity. 

When paired with the Alpaca Benro Polaris Driver, Alpaca Pilot unlocks advanced control capabilities for both the Driver and the Benro Polaris mount - all within a single, streamlined interface. It goes beyond the standard Alpaca protocol by exposing powerful driver-specific features such as connection management, calibration tools, test report generation, and real-time diagnostics and analysis. This expanded functionality enables deeper insight, precision tuning, and robust system oversight for users who demand more than basic mount control.

## Installation of Alpaca Pilot
The Alpaca Pilot is bundled within the Alpaca Benro Polaris Driver and no additional installation is required. To access Alpaca Pilot you can use the Setup Button in Nina, or you can open the Alpaca Pilot directly from within a web browser or mobile app.

## Development of Alpaca Pilot
The following information is intended for technical specialists involved in the development of Alpaca Pilot and can be ignored by the majority of users.
### Install the dependencies

```bash
yarn
# or
npm install
```

#### Start the app in development mode (hot-code reloading, error reporting, etc.)

```bash
quasar dev
```

#### Lint the files

```bash
yarn lint
# or
npm run lint
```

#### Format the files

```bash
yarn format
# or
npm run format
```

#### Build the app for production

```bash
quasar build
```

#### Customize the configuration

See [Configuring quasar.config.js](https://v2.quasar.dev/quasar-cli-vite/quasar-config-js).
