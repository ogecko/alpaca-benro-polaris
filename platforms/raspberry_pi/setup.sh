#!/bin/bash -e
#
# This bootstraps the unified application on a Raspberry Pi.
#
AP_SSID="alpaca-hotspot"
DEFAULT_AP_PASSWORD="alpacabp"
STA_SSID=""
STA_PASSWORD=""
AP_PASSWORD=""
BRANCH="main"
REPO_DIR="alpaca-benro-polaris"
REPO_URL="https://github.com/ogecko/alpaca-benro-polaris.git"

define_usage() {
    read -r -d '' USAGE <<EOM || true

Usage: $0 [-n sta_ssid] [-w sta_password] [-a ap_ssid] [-p ap_password] [-h] [branch]

Options:
    -n <ssid>      Wifi network SSID to prioritise in Station Mode (STA) on wlan0 --
                   creates it (using -w as its password) if it doesn't already exist,
                   otherwise just prioritises the existing one and ignores -w. Default:
                   whichever network wlan0 is currently connected to (on a freshly-
                   imaged Pi, that's already the Raspberry Pi Imager's own network) --
                   so -n is normally only needed to add an *additional* known network.
    -w <password>  Password for the network named by -n (only used when creating it).
    -a <ssid>      SSID for the Access Point (AP) fallback wlan0 broadcasts when no
                   known STA network is in range, e.g. at a dark site.
                   (default: ${AP_SSID})
    -p <password>  Password for the AP fallback, min 8 chars for WPA2.
                   (default: prompted interactively, or '${DEFAULT_AP_PASSWORD}' if
                   not running in a terminal)
    -h             Print this help and exit.
    branch         Git branch to install, as a plain trailing argument.
                   (default: ${BRANCH})

EOM
}

help_exit() {
    echo "${USAGE}"
    [ "${1:?}" == "true" ] && exit 0
    exit 1
}

parse_args() {
    while getopts ":n:w:a:p:h" opt; do
        case "$opt" in
            n) STA_SSID="$OPTARG" ;;
            w) STA_PASSWORD="$OPTARG" ;;
            a) AP_SSID="$OPTARG" ;;
            p) AP_PASSWORD="$OPTARG" ;;
            h) help_exit "true" ;;
            \?) echo "Error: invalid option (-$OPTARG)."; help_exit "false" ;;
            :)  echo "Error: -$OPTARG requires an argument."; help_exit "false" ;;
        esac
    done
    shift $((OPTIND - 1))
    BRANCH="${1:-$BRANCH}"   # First remaining (non-flag) argument is the branch name
}

define_usage
parse_args "$@"

# Access Point (AP) mode fallback (see ==SETUP== step below) -- wlan0 broadcasts its own
# network so you can still reach the Pi from a phone/laptop at a dark site with no Station
# Mode (STA) network in range. wlan1 (TPLink) keeps connecting to the Polaris either way.
if [ -z "$AP_PASSWORD" ] && [ -t 0 ]; then
    read -r -p "Password for AP mode fallback '$AP_SSID' (min 8 chars) [default: $DEFAULT_AP_PASSWORD]: " AP_PASSWORD
fi
if [ -z "$AP_PASSWORD" ] || [ "${#AP_PASSWORD}" -lt 8 ]; then
    [ -n "$AP_PASSWORD" ] && echo "Password too short for WPA2 (min 8 characters) -- using default instead."
    AP_PASSWORD="$DEFAULT_AP_PASSWORD"
fi

echo "==SETUP== Alpaca Benro Polaris Raspberry Pi Setup ======================================."

echo "==SETUP== 1. Update the software on the system, and install dependencies needed for git and uv."
for pkg in git curl; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        echo "Installing $pkg..."
        sudo apt-get update -qq   # run update only if a package is missing
        sudo apt-get install --yes "$pkg"
    else
        echo "$pkg is already installed — skipping."
    fi
done

echo "==SETUP== 2. Clone/Fetch the alpaca-benro-polaris software from Git-Hub."
if [ -d "$REPO_DIR/.git" ]; then
    echo "Directory exists — fetching latest updates..."
    cd "$REPO_DIR"
    git restore driver/config.toml
    git fetch --all
    git checkout "$BRANCH"
    git pull
else
    echo "Directory does not exist — cloning fresh copy..."
    git clone --branch "$BRANCH" "$REPO_URL"
    cd "$REPO_DIR"
fi
src_home=$(pwd)
mkdir -p logs
mkdir -p data

echo "==SETUP== 3. Install uv, adding it to ~/.bashrc."
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
source "$HOME/.local/bin/env"
if ! grep -q "alpaca-benro-polaris edits" ~/.bashrc; then
    echo "Adding venv auto-activation to ~/.bashrc..."
    cat <<_EOF >> ~/.bashrc

# start of alpaca-benro-polaris edits
if [ -d "$src_home/.venv" ]; then
    source "$src_home/.venv/bin/activate"
    cd "$src_home"
fi
# end of alpaca-benro-polaris edits

_EOF
else
    echo "~/.bashrc already contains venv activation — skipping."
fi

echo "==SETUP== 4. Sync the python dependencies needed for the application with uv (creates $src_home/.venv)."
uv sync --no-dev --locked --no-build-package numpy --no-build-package scipy
source "$src_home/.venv/bin/activate"



echo "==SETUP== 5. Updating config.toml with 'alpaca_pilot_http_port = 8080' and 'alpaca_pilot_https_port = 8443' =="
# Ports below 1024 need root, and app_web.py checks both the http and https ports are
# bindable at startup regardless of enable_https, so both need to move off the privileged range.
sudo sed -i -E \
    -e 's/^(alpaca_pilot_http_port[[:space:]]*=[[:space:]]*)80([[:space:]]|$)/\18080\2/' \
    -e 's/^(alpaca_pilot_https_port[[:space:]]*=[[:space:]]*)443([[:space:]]|$)/\18443\2/' \
    "$src_home/driver/config.toml"


echo "==SETUP== 6. Ensure Bluetooth is powered on, needed for BLE communication with the Polaris."
for rfk in /sys/class/rfkill/rfkill*; do
    if [ "$(cat "$rfk/type" 2>/dev/null)" = "bluetooth" ] && [ "$(cat "$rfk/soft" 2>/dev/null)" = "1" ]; then
        echo "Bluetooth is soft-blocked — unblocking $rfk..."
        echo 0 | sudo tee "$rfk/soft" > /dev/null
    fi
done
if command -v hciconfig >/dev/null 2>&1; then
    sudo hciconfig hci0 up 2>/dev/null || true
fi

echo "==SETUP== 7. Force the Bluetooth adapter into LE-only mode, needed for reliable BLE to the Polaris."
# The Polaris's own bluetoothd advertises classic-audio profiles (Source/Sink/Media/
# Broadcast, confirmed on the mount's own /app/bluetooth/config/main.conf) that it
# never actually services -- almost certainly leftover reference-BSP config. BlueZ,
# correctly per spec, tries a classic BR/EDR connection alongside the LE one for any
# device advertising dual-mode capability; that classic attempt fails and takes the
# whole Connect() down with it ("br-connection-profile-unavailable"), even though the
# LE/GATT side works fine on its own. Windows/iOS/Android's BLE stacks are LE-only by
# construction and never hit this -- it isn't specific to this driver. Forcing the
# Pi's own adapter into LE-only mode stops BlueZ from ever attempting the classic
# bearer, which is what actually breaks the connection.
BT_CONF="/etc/bluetooth/main.conf"
if ! grep -q "^ControllerMode" "$BT_CONF" 2>/dev/null; then
    echo "Setting ControllerMode = le in $BT_CONF..."
    sudo sed -i '/^\[General\]/a ControllerMode = le' "$BT_CONF"
    sudo systemctl restart bluetooth
    sleep 2
    sudo hciconfig hci0 up 2>/dev/null || true
else
    echo "ControllerMode already set in $BT_CONF — skipping."
fi

echo "==SETUP== 8. Grant passwordless nmcli access, needed for join_wifi.py to join the Polaris hotspot."
# NetworkManager's own polkit rule only allows unauthenticated connection
# changes from a "local and active" seat session -- the polaris-driver
# service (User=pi, no seat) never qualifies, so join_wifi.py's nmcli calls
# would otherwise hang waiting for a sudo password that never comes.
NMCLI_SUDOERS="/etc/sudoers.d/polaris-nmcli"
NMCLI_PATH="$(command -v nmcli)"
echo "pi ALL=(ALL) NOPASSWD: ${NMCLI_PATH}" | sudo tee "$NMCLI_SUDOERS" > /dev/null
sudo chmod 440 "$NMCLI_SUDOERS"
sudo visudo -cf "$NMCLI_SUDOERS"

echo "==SETUP== 9. Configure wlan0 for Station Mode (STA) at home, falling back to Access Point Mode (AP) at a dark site."
# nmcli's connection-list view has no direct SSID column, so finding a wlan0 profile by
# SSID means checking each profile's own 802-11-wireless.ssid property individually.
find_wlan0_conn_by_ssid() {
    for name in $(nmcli -t -f NAME connection show); do
        if [ "$(nmcli -g 802-11-wireless.ssid connection show "$name" 2>/dev/null)" = "$1" ]; then
            echo "$name"
            return 0
        fi
    done
    return 1
}

# Find (or create) the STA connection profile to prioritise. If -n named a specific
# SSID: use the existing wlan0 profile for it if one exists (ignoring -w -- we don't
# overwrite a working password just because -w was also passed), otherwise create a
# new one using -w as its password (left open if -w wasn't given). If -n wasn't given
# at all, fall back to whichever wlan0 connection is currently active -- on a
# freshly-imaged Pi, that's already whatever network the Imager itself joined.
STA_CONN=""
if [ -n "$STA_SSID" ]; then
    STA_CONN=$(find_wlan0_conn_by_ssid "$STA_SSID") || true
    if [ -z "$STA_CONN" ]; then
        STA_CONN="sta-$STA_SSID"
        sudo nmcli connection add type wifi ifname wlan0 con-name "$STA_CONN" autoconnect yes ssid "$STA_SSID"
        [ -n "$STA_PASSWORD" ] && sudo nmcli connection modify "$STA_CONN" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$STA_PASSWORD"
        echo "Added new STA network '$STA_SSID' on wlan0."
    else
        echo "STA network '$STA_SSID' already exists as '$STA_CONN'."
    fi
else
    STA_CONN=$(nmcli -t -f NAME,DEVICE,TYPE connection show --active | awk -F: '$2=="wlan0" && $3=="802-11-wireless" {print $1; exit}')
fi
if [ -n "$STA_CONN" ]; then
    # Pin explicitly to wlan0 and give it priority over the AP fallback below, so
    # NetworkManager always prefers it when the network is in range. Raspberry Pi
    # Imager's netplan-rendered connection does NOT set connection.interface-name by
    # default -- confirmed live: without this, nmcli can (and did) hand this profile to
    # whichever wifi device happens to be free, including wlan1 (meant only for the
    # Polaris), scrambling both interfaces' roles.
    sudo nmcli connection modify "$STA_CONN" connection.interface-name wlan0 connection.autoconnect-priority 10
    echo "Pinned STA connection '$STA_CONN' to wlan0 with priority 10 (preferred over AP mode fallback)."
else
    echo "No active wlan0 connection found -- skipping STA setup (AP mode fallback will still be configured)."
fi

AP_CONN="alpaca-ap-fallback"
if ! nmcli -t -f NAME connection show | grep -qx "$AP_CONN"; then
    sudo nmcli connection add type wifi ifname wlan0 con-name "$AP_CONN" autoconnect yes ssid "$AP_SSID"
    echo "Created AP mode fallback connection '$AP_CONN'."
else
    echo "AP mode fallback connection '$AP_CONN' already exists — updating it."
fi
sudo nmcli connection modify "$AP_CONN" \
    connection.interface-name wlan0 \
    802-11-wireless.mode ap 802-11-wireless.band bg \
    ipv4.method shared \
    wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$AP_PASSWORD" \
    connection.autoconnect-priority 0
echo "AP mode fallback '$AP_SSID' will activate automatically on wlan0 whenever no known STA network is in range."

SERVICE_FILE="/etc/systemd/system/polaris-driver.service"
echo "==SETUP== 10. Set up [systemd] services to start the Polaris Driver at boot time."

sudo systemctl stop polaris-driver.service 2>/dev/null || true
sudo systemctl disable polaris-driver.service 2>/dev/null || true
sudo rm -f "$SERVICE_FILE"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Polaris Driver Startup Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=${src_home}/driver
ExecStart=${src_home}/.venv/bin/python3 ${src_home}/driver/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "==SETUP== 11. Starts the polaris-driver service."
sudo systemctl daemon-reload
sudo systemctl enable polaris-driver.service
sudo systemctl restart polaris-driver.service

cat <<_EOF
-------------------------------------------------------------------
Alpaca Benro Polaris Setup Complete 
                                     
You can:
* Check the service status with:  sudo systemctl status polaris-driver
* Stop the service with:          sudo systemctl stop polaris-driver
* Start the service with:         sudo systemctl start polaris-driver
* View the logs with:             journalctl -u polaris-driver -f
* access Alpaca Pilot via:        http://$(hostname):8080             

-------------------------------------------------------------------
_EOF
