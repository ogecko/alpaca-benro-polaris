[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Docker Installation Guide
Docker provides a portable way to run the driver on any OS and architecture without installing Python or its dependencies directly on the host.

# Install docker

## Linux / Raspberry Pi
Install Docker Engine using the [official instructions](https://docs.docker.com/engine/install/) for your distribution, e.g. `sudo apt install docker.io`.

## Windows
1. **Install WSL2.** Open PowerShell **as Administrator** and run:
   ```
   wsl --install
   ```
   Reboot if prompted, then let Ubuntu finish its first-run setup and create a Unix username/password when asked.

2. **Open a WSL terminal** — run `wsl` from PowerShell/cmd, or launch "Ubuntu" from the Start menu — and install Docker Engine directly inside it:
   ```
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   ```
   Close and reopen your WSL terminal afterwards.

3. **Clone the repository into the WSL filesystem**, not under `/mnt/c/...` — the Windows drive is much slower and doesn't preserve the executable bit `run.sh` needs:
   ```
   git clone https://github.com/ogecko/alpaca-benro-polaris.git ~/alpaca-benro-polaris
   cd ~/alpaca-benro-polaris
   ```

Continue with **Build** and **Run** below from this same WSL terminal.

## macOS
Install Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop/).

# Build
`run.sh`, `util.sh`, and `entrypoint.sh` aren't checked into git as executable, so mark them runnable the first time you check out the repo:
```
chmod +x platforms/docker/run.sh platforms/docker/util.sh platforms/docker/entrypoint.sh
```

The image is built automatically the first time you run `run.sh`. To force a rebuild (e.g. after pulling changes), pass `-b`:
```
./platforms/docker/run.sh -b -t "America/Vancouver"
```

# Run
Run the following from a terminal, setting your local time zone using one of the `TZ identifier` options listed [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones). For example:
```
./platforms/docker/run.sh -t "America/Vancouver"
```
This starts the driver, reachable at `http://localhost` from the same computer, or at your computer's IP address from any other device on your network.

| Port  | Protocol | Service                             |
|-------|----------|--------------------------------------|
| 5555  | TCP      | Alpaca REST API                     |
| 5556  | TCP      | Alpaca Pilot SocketIO               |
| 80    | TCP      | Alpaca Pilot Web UI (HTTP)          |
| 443   | TCP      | Alpaca Pilot Web UI (HTTPS)         |
| 32227 | UDP      | Alpaca Discovery                    |
| 10001 | TCP      | Stellarium / SynScan Telescope API  |
| 5353  | UDP      | mDNS (advertises `ap.local`)        |

If your computer needs a dedicated USB WiFi adapter to talk to the Benro Polaris (see [Hardware](./hardware.md#using-a-laptop-with-stellarium-desktop)), just connect to the Polaris's `polaris_XXXXXX` hotspot on that adapter as normal, the driver reaches it over whatever network your computer is on.

## Connecting Alpaca Pilot to the Docker Containers Driver
To reach the driver from another device, use your host computer's own network IP address, not the address shown in the driver's mDNS startup log, which reports Docker's internal address.

- **Windows/WSL:** `ipconfig`
- **macOS/Linux/Raspberry Pi:** `ip addr` or `hostname -I`

## Connecting via mDNS and http://ap.local
To reach the driver via the mDNS name, you will need to be on the same network as the Docker container. By default Docker isolates the containers network through a NAT. To overcome this you can use the `-n` option to use host networking.

On **Linux and Raspberry Pi**, running with `-n` make the container share your computer's real network directly. This should allow mDNS to work correctly:
```
./platforms/docker/run.sh -n -t "America/Vancouver"
```

On **Windows**, `-n` doesn't extend past WSL2's own network, it won't reach other devices like an iPad, since WSL2 sits behind an extra layer of network address translation that mDNS can't cross. There's currently no way to make `ap.local` reachable from another device when running under WSL2; use your computer's IP address instead (see above). `-n` isn't available on **macOS** at all.

If you're running more than one instance of the driver on your network (e.g. one on a mini-PC, one in Docker), give each a different hostname in the Alpaca Pilot **Network Settings**. Otherwise they'll silently compete for the same `ap.local` name and which one you reach becomes unpredictable.

# Configuration
Alpaca Pilot saves any setting you change as an overlay on top of the shipped defaults, and the driver writes generated data (calibration, presets, catalog cache, TLS certs, etc.) alongside it. All of this configuration information is stored in `platforms/docker/data` on the host computer. So it survives container restarts and image rebuilds. You should never need to edit `driver/config.toml` directly.

Run `./platforms/docker/run.sh -h` for the full list of options.
