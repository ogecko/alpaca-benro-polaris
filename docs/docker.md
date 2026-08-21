[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)



# Docker Installation Guide

Docker provides a portable and consistent way to run the driver across supported operating systems and hardware architectures. Instead of installing Python and the driver's dependencies directly on the host system, Docker packages the driver and its runtime environment into a container.

This approach keeps the host system clean, makes installation and updates more predictable, and helps ensure that the driver behaves consistently across different platforms. Docker is particularly useful on systems such as Raspberry Pi, where managing Python versions and native dependencies can otherwise require additional setup.

Follow the instructions below for your operating system. **Windows users should complete the additional WSL2, networking, and firewall configuration** to allow the driver's network services to be accessed by other devices on the local network.



# 1. Install Docker

## Linux / Raspberry Pi

Install Docker Engine using the [official instructions](https://docs.docker.com/engine/install/) for your distribution. For example:

```bash
sudo apt install docker.io
```

## macOS

Install Docker Desktop from [Docker](https://www.docker.com/products/docker-desktop/).

## Windows

The Windows setup uses WSL2, which provides a Linux environment for running Docker Engine. The additional networking configuration below allows the driver's network services to be reached from other devices on your local network, such as an iPad or another PC.

   1. Install WSL2

      Open PowerShell **as Administrator** and run:

      ```powershell
      wsl --install
      ```

      Windows may prompt you to restart. If so, restart before continuing.

   2. Enable WSL2 mirrored networking

      Mirrored networking makes the driver reachable from other devices on your local network, rather than only from the Windows host.

      Create `%USERPROFILE%\.wslconfig` with mirrored networking enabled:

      ```powershell
      @"
      [wsl2]
      networkingMode=mirrored
      "@ | Set-Content -Path "$env:USERPROFILE\.wslconfig"
      ```

      Restart WSL to apply the configuration:

      ```powershell
      wsl --shutdown
      ```

   3. Allow the driver through Windows Firewall

      Unlike a native Python installation, the Docker-based driver does not automatically prompt Windows to create firewall rules for its network services.

      Open PowerShell **as Administrator** and run:

      ```powershell
      New-NetFirewallRule -DisplayName "Alpaca Benro Polaris (TCP)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80,443,5555,5556,10001 -Profile Private

      New-NetFirewallRule -DisplayName "Alpaca Benro Polaris (UDP)" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 32227 -Profile Private
      ```

      The Windows built-in **mDNS (UDP-In)** rule normally already allows UDP port 5353, so no additional mDNS rule is required.

      The `-Profile Private` option is appropriate for most home LANs. Check your current network category under **Settings > Network & Internet > [your adapter]** and adjust the firewall rules if your network uses a different profile.

   4. Install Docker Engine in WSL2

      Open a WSL terminal by either running `wsl` from PowerShell or Command Prompt, or launching **Ubuntu** from the Start menu.

      Install Docker Engine:

      ```bash
      curl -fsSL https://get.docker.com | sh
      sudo usermod -aG docker $USER
      ```

      Close and reopen the WSL terminal so the group membership change takes effect.

# 2. Clone 

   Clone the Alpaca Benro Polaris repository into a subfolder under your home directory. 

   ```bash
   git clone https://github.com/ogecko/alpaca-benro-polaris.git ~/alpaca-benro-polaris
   cd ~/alpaca-benro-polaris
   ```
   > Note: On Windows WSL, we do not recommend cloning to `/mnt/c/...`. The WSL filesystem provides better performance for the driver and preserves the executable permission required by `run.sh`. Continue with **Build** and **Run** below, using this same WSL terminal.



# 3. Build

The Docker scripts in the repository need to be executable before they can be run. Git does not preserve the executable permission for these files, so mark them as executable the first time you check out the repository:

```bash
chmod +x platforms/docker/run.sh platforms/docker/util.sh platforms/docker/entrypoint.sh
```

The Docker image is built automatically the first time you run `run.sh`. You normally do not need to build it separately.

To force the image to be rebuilt (for example, after pulling changes that affect the Docker image) use the `-b` option:

```bash
./platforms/docker/run.sh -b -t "America/Vancouver"
```

The `-t` option sets the driver's local time zone. Replace `America/Vancouver` with your own [TZ database time zone](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

# 4. Run

Start the driver with:

```bash
./platforms/docker/run.sh -t "America/Vancouver"
```

Replace the time zone with the one appropriate for your location.

Once started, the Alpaca Pilot is available at `http://localhost` on the computer running Docker. Other devices on the same network can connect using the host computer's network IP address or the mDNS name `http://ap.local`.

The container exposes the following services:

|  Port | Protocol | Service                            |
| ----: | :------: | ---------------------------------- |
|    80 |    TCP   | Alpaca Pilot Web UI (HTTP)         |
|   443 |    TCP   | Alpaca Pilot Web UI (HTTPS)        |
|  5555 |    TCP   | Alpaca REST API                    |
|  5556 |    TCP   | Alpaca Pilot Socket.IO             |
| 10001 |    TCP   | Stellarium / SynScan Telescope API |
| 32227 |    UDP   | Alpaca Discovery                   |
|  5353 |    UDP   | mDNS — advertises `ap.local`       |



# 5. Configuration

Alpaca Pilot settings are stored as an overlay on top of the driver's shipped default configuration. The driver also generates and stores persistent data such as:

* calibration data
* presets
* catalog caches
* TLS certificates
* other runtime state

For Docker installations, this data is stored on the host in:

```text
platforms/docker/data
```

Because this directory is outside the Docker container, the data survives:

* container restarts
* Docker image rebuilds
* removal and recreation of the container

You therefore **should not normally need to edit `driver/config.toml` directly**. Configuration changes should be made through Alpaca Pilot wherever possible.

For a complete list of available command-line options, run:

```bash
./platforms/docker/run.sh -h
```

