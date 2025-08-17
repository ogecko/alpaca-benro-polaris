# Alpaca Pilot (Position Control Reimagined)

Alpaca Pilot is a modern control interface for astronomical mounts, designed to streamline and reimagine the way users interact with Alpaca-compatible devices. With intuitive dashboards, responsive controls, and real-time telemetry visualization, Alpaca Pilot empowers observers to manage slewing, rotating, targeting, tracking, guiding, and alignment with confidence and clarity. 

When paired with the Alpaca Benro Polaris Driver, Alpaca Pilot unlocks advanced control capabilities for both the Driver and the Benro Polaris mount - all within a single, streamlined interface. It goes beyond the standard Alpaca protocol by exposing powerful driver-specific features such as connection management, calibration tools, test report generation, and real-time diagnostics and analysis. This expanded functionality enables deeper insight, precision tuning, and robust system oversight for users who demand more than basic mount control.

## Installation of Alpaca Pilot
The Alpaca Pilot is bundled within the Alpaca Benro Polaris Driver and no additional installation is required. To access Alpaca Pilot you can use the Setup Button in Nina, or you can open the Alpaca Pilot directly from within a web browser or mobile app.

## Development of Alpaca Pilot
The following information is intended for technical specialists involved in the development of Alpaca Pilot and can be ignored by the majority of users.
### Install Node.js on your Platform
Download and run the prebuild Node.js package for your platform from https://nodejs.org/en/download. On Windows you should click on the green button `Windows Installer (.msi)`
1. Click Next on the Node.js Setup Wizard.
2. Accept the License Agreement Terms and click Next.
3. Accept the default installation directory and click Next.
4. Accept the default setup and click Next.
5. No need to isntall Native Modules, click Next.
6. Click Install.
7. Accept the User Account Control request, click Yes.
8. Click Finish.

Ensure node.js has been added to your PATH environment variable for all users (local and VSCode SSH remote).
1. Open PowerShell with Administrator privellages
2. Execute the following command
    ```
    [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\nodejs", "Machine")
    ```

Allow PowerShell to execute scripts like npm.
1. Open PowerShell as Administrator
2. Run:
    ```
    Set-ExecutionPolicy RemoteSigned
    ```
3. When prompted, type Y and press Enter

Confirm that you can run the following commands
```
node -v
npm -v
```
### Install the dependencies
Run the following command to install the node.js package dependancies.

```bash
npm install
```

#### Start the app in development mode (hot-code reloading, error reporting, etc.)

```bash
quasar dev
```

#### Build the app for production (bundle located at pilot/dist/spa), served by Alpaca Driver.

```bash
quasar build
```

#### Lint the files

```bash
npm run lint
```

#### Format the files

```bash
npm run format
```



#### Customize the configuration

See [Configuring quasar.config.js](https://v2.quasar.dev/quasar-cli-vite/quasar-config-js).
