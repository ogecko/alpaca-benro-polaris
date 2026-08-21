[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Docker Installation Guide
Docker provides a portable way to run the driver on any OS and architecture without installing Python or its dependencies directly on the host.

# Install docker
This should work with any version of Docker (e.g. Docker Desktop, docker.io, docker-ce, etc.).

If you don't have Docker installed and don't have a preference, then [follow the official instructions](https://docs.docker.com/get-docker/). Windows users, see the [Windows (WSL2) setup](#windows-wsl2-setup) section below first.  Docker on Windows requires WSL2, and `run.sh` needs to run from inside it.

## Windows (WSL2) setup
Docker Desktop on Windows runs containers inside WSL2 (Windows Subsystem for Linux), and `run.sh`/`util.sh`/`entrypoint.sh` are bash scripts, so you'll run everything from a WSL terminal rather than PowerShell or cmd.

1. **Install WSL2.** Open PowerShell **as Administrator** and run:
   ```
   wsl --install
   ```
   This installs WSL2 and, by default, an Ubuntu distribution. Reboot if prompted, then let Ubuntu finish its first-run setup and create a Unix username/password when asked.

2. **Install Docker Desktop.** Download it from [docker.com](https://www.docker.com/products/docker-desktop/) and run the installer with default options. During setup (or afterwards in **Settings → Resources → WSL Integration**), make sure integration is enabled for your Ubuntu distribution.

3. **Open a WSL terminal** for everything below. Either run `wsl` from PowerShell/cmd, or launch "Ubuntu" from the Start menu.

4. **Clone the repository into the WSL filesystem**, not under `/mnt/c/...`. Cloning onto the Windows drive works, but it's much slower and NTFS doesn't reliably preserve the executable bit the docker scripts need (you'd hit the same `chmod +x` problem repeatedly). Clone into your WSL home directory instead:
   ```
   git clone https://github.com/ogecko/alpaca-benro-polaris.git ~/alpaca-benro-polaris
   cd ~/alpaca-benro-polaris
   ```
   (If `git` isn't installed yet: `sudo apt-get update && sudo apt-get install -y git`.)

Continue with **Build** and **Run** below from this same WSL terminal.

# Build
`run.sh`, `util.sh`, and `entrypoint.sh` aren't checked into git as executable, so the first time you check out the repo you'll need to mark them runnable:
```
chmod +x platforms/docker/run.sh platforms/docker/util.sh platforms/docker/entrypoint.sh
```

The image is built automatically the first time you run `run.sh`. To force a rebuild (e.g. after pulling changes), pass `-b`:
```
./platforms/docker/run.sh -b -t "America/Vancouver"
```
The build uses [uv](https://docs.astral.sh/uv/) to install the exact Python version and dependencies pinned in `pyproject.toml`/`uv.lock`, so it doesn't need anything pre-installed on the host beyond Docker itself.

# Run
Run the following from a terminal, setting your local time zone using one of the `TZ identifier` options listed [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones). For example:
```
./platforms/docker/run.sh -t "America/Vancouver"
```
This publishes the ports the driver needs, and bind-mounts a `platforms/docker/data` directory into the container:

| Port  | Protocol | Service                          |
|-------|----------|-----------------------------------|
| 5555  | TCP      | Alpaca REST API                   |
| 5556  | TCP      | Alpaca Pilot SocketIO              |
| 80    | TCP      | Alpaca Pilot Web UI (HTTP)         |
| 443   | TCP      | Alpaca Pilot Web UI (HTTPS)        |
| 32227 | UDP      | Alpaca Discovery                  |
| 10001 | TCP      | Stellarium / SynScan Telescope API |
| 5353  | UDP      | mDNS (advertises `ap.local`, etc.) |

> **Note:** mDNS relies on multicast (224.0.0.251), which Docker's default bridge network does not reliably forward even with the port published above. If `http://ap.local` doesn't resolve from another device, use the host's IP address directly, or run the container with `--network host` (Linux only) for full mDNS support.

# Configuration
There's no config file to prepare beforehand as the image ships with the driver's default `config.toml`. Once the container is running, open the Alpaca Pilot web UI at `http://localhost` (or `https://localhost` if you later enable HTTPS) and set your Benro Polaris's WiFi hotspot IP address, along with anything else, from there.

Pilot saves anything you change as an overlay on top of the shipped defaults, and the driver writes generated data (calibration, presets, catalog cache, TLS certs, etc.) alongside it — all of it lands in `platforms/docker/data` on the host, so it survives container restarts and image rebuilds. You should never need to edit `driver/config.toml` directly.

Run `./platforms/docker/run.sh -h` for the full list of options.
