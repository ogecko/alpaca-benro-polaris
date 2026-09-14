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
    -n <ssid>      Defines the network SSID for the Alpaca Station Mode Wifi connection. 
                   Normally only needed to add *additional* known networks to automatically join.
                   (default:the network SSID defined in the freshly-imaged Pi). 
    -w <password>  Password for the network named by -n (only used when creating it).

    -a <ssid>      Defines the network SSID for the Alpaca Hotspot Fallback connection on wlan0. 
                   Only used when no known STA network is in range, e.g. at a dark site.
                   (default: ${AP_SSID})
    -p <password>  Password for the network named by -a, min 8 chars for WPA2.
                   (default: prompted interactively, or '${DEFAULT_AP_PASSWORD}' if not running in a terminal)

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

if [ ! -f pyproject.toml ]; then
    echo "Error: branch '$BRANCH' doesn't have a pyproject.toml >&2
    echo "This script only supports Alpaca Driver v2.2 Beta 5 or above." >&2
    echo "'$BRANCH' is either an older version or an unrelated branch." >&2
    echo "Try a different version/branch, e.g.:" >&2
    echo "    $0 dev2_2" >&2
    exit 1
fi

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

# Any currently-active Wifi connection except our own AP fallback / Polaris profiles --
# used to find "the home network" when -n wasn't given, regardless of which radio
# (wlan0 or wlan1) happens to be carrying it right now. Deliberately not restricted to
# wlan0 -- if this profile has already drifted onto wlan1 (see netplan note below),
# restricting the search to wlan0 would never find it, and this whole step would
# silently no-op forever instead of fixing it.
find_active_home_conn() {
    nmcli -t -f NAME,TYPE connection show --active | awk -F: '$2=="802-11-wireless"{print $1}' \
        | grep -vx 'alpaca-hotspot-fallback' | grep -v '^polaris' | head -n1
}

# Raspberry Pi Imager's own Wifi setup is rendered via netplan (connection names
# starting with "netplan-"), which regenerates its NetworkManager profile straight from
# /etc/netplan/*.yaml on every `netplan apply` -- including at every boot -- silently
# wiping out any connection.interface-name pin applied via nmcli. That's what let this
# profile drift onto wlan1 (meant only for the Polaris) in the first place: pinning it
# worked until the next reboot, then reverted. Rather than fight netplan forever, copy
# its SSID/password into our own plain nmcli profile (netplan never touches those) and
# retire the netplan one for good.
#
# Deleting the YAML source is just a file removal -- it doesn't touch the live
# connection, so it's safe to do here in the foreground even while that connection is
# actively carrying this very SSH session (unlike the nmcli teardown below, which is
# not safe to do here -- see the NETPLAN_MIGRATE block further down).
retire_netplan_yaml() {
    local name="$1" uuid f
    uuid=$(nmcli -g connection.uuid connection show "$name" 2>/dev/null)
    [ -n "$uuid" ] || return 0
    for f in /etc/netplan/*.yaml; do
        [ -f "$f" ] && sudo grep -q "$uuid" "$f" 2>/dev/null && sudo rm -f "$f"
    done
}

# Find (or create) the STA connection profile to prioritise. If -n named a specific
# SSID: use the existing wlan0 profile for it if one exists (ignoring -w -- we don't
# overwrite a working password just because -w was also passed), otherwise create a
# new one using -w as its password (left open if -w wasn't given). If -n wasn't given
# at all, fall back to whichever Wifi connection is currently active -- on a
# freshly-imaged Pi, that's already whatever network the Imager itself joined. Either
# way, a netplan-rendered match gets migrated to a plain profile (see above) rather
# than reused directly.
STA_CONN=""
NETPLAN_MIGRATE=""
if [ -n "$STA_SSID" ]; then
    SRC_CONN=$(find_wlan0_conn_by_ssid "$STA_SSID") || true
    if [ -z "$SRC_CONN" ]; then
        STA_CONN="alpaca-station-$STA_SSID"
        sudo nmcli connection add type wifi ifname wlan0 con-name "$STA_CONN" autoconnect yes ssid "$STA_SSID"
        [ -n "$STA_PASSWORD" ] && sudo nmcli connection modify "$STA_CONN" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$STA_PASSWORD"
        echo "Added new STA network '$STA_SSID' on wlan0."
    elif [[ "$SRC_CONN" == netplan-* ]]; then
        STA_CONN="alpaca-station-$STA_SSID"
        if ! nmcli -t -f NAME connection show | grep -qx "$STA_CONN"; then
            SRC_PSK=$(sudo nmcli -s -g 802-11-wireless-security.psk connection show "$SRC_CONN" 2>/dev/null)
            PW="${STA_PASSWORD:-$SRC_PSK}"
            sudo nmcli connection add type wifi ifname wlan0 con-name "$STA_CONN" autoconnect yes ssid "$STA_SSID"
            [ -n "$PW" ] && sudo nmcli connection modify "$STA_CONN" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PW"
        fi
        NETPLAN_MIGRATE="$SRC_CONN"
        retire_netplan_yaml "$SRC_CONN"
    else
        STA_CONN="$SRC_CONN"
        echo "STA network '$STA_SSID' already exists as '$STA_CONN'."
    fi
else
    SRC_CONN=$(find_active_home_conn) || true
    if [ -n "$SRC_CONN" ] && [[ "$SRC_CONN" == netplan-* ]]; then
        SRC_SSID=$(nmcli -g 802-11-wireless.ssid connection show "$SRC_CONN")
        STA_CONN="alpaca-station-$SRC_SSID"
        if ! nmcli -t -f NAME connection show | grep -qx "$STA_CONN"; then
            SRC_PSK=$(sudo nmcli -s -g 802-11-wireless-security.psk connection show "$SRC_CONN" 2>/dev/null)
            sudo nmcli connection add type wifi ifname wlan0 con-name "$STA_CONN" autoconnect yes ssid "$SRC_SSID"
            [ -n "$SRC_PSK" ] && sudo nmcli connection modify "$STA_CONN" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$SRC_PSK"
        fi
        NETPLAN_MIGRATE="$SRC_CONN"
        retire_netplan_yaml "$SRC_CONN"
    else
        STA_CONN="$SRC_CONN"
    fi
fi
if [ -n "$STA_CONN" ]; then
    # Pin explicitly to wlan0 and give it priority over the AP fallback below, so
    # NetworkManager always prefers it when the network is in range. Safe to run even
    # while some other connection is currently active on wlan0 -- this only sets
    # metadata, it doesn't force a live switch.
    sudo nmcli connection modify "$STA_CONN" connection.interface-name wlan0 connection.autoconnect-priority 10
    echo "Pinned STA connection '$STA_CONN' to wlan0 with priority 10 (preferred over AP mode fallback)."
else
    echo "No active Wifi connection found -- skipping STA setup (AP mode fallback will still be configured)."
fi

AP_CONN="alpaca-hotspot-fallback"
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

if [ -n "$NETPLAN_MIGRATE" ]; then
    echo "'$NETPLAN_MIGRATE' is netplan-managed and would silently re-unpin itself on the next reboot -- retiring it now that '$STA_CONN' has taken over."
    echo "NOTE: if that network is what's carrying this SSH session right now, it may drop for a few seconds while it switches over -- that's expected, just reconnect."
    # Deleting this connection and forcing the new one onto wlan0 may drop the very SSH
    # session running this script, if that's the network carrying it. A plain
    # `cmd & disown` does NOT survive that: once sshd notices the session's connection
    # die, systemd-logind tears down the whole login session's cgroup, which kills
    # every process in it -- disowned or not, since disown only detaches from the
    # shell's own job control, not from that cgroup. `systemd-run` starts a transient
    # unit in its own scope, outside the login session, so it survives regardless.
    sudo systemd-run --unit="alpaca-sta-migrate-$$" --collect -- bash -c "
        nmcli connection delete $(printf %q "$NETPLAN_MIGRATE")
        nmcli connection up $(printf %q "$STA_CONN") ifname wlan0
    "
fi

echo "==SETUP== 10. Disable Wifi power-saving, which can make the onboard chip randomly stop responding entirely."
# The Pi's onboard BCM43430 chip (Zero W / Zero 2 W) is known to sometimes hang and
# drop off the network completely -- neither Station nor the AP fallback reachable --
# until power-cycled, when its power-saving mode is left enabled. This is worse
# combined with the heavy Bluetooth/BLE coexistence this driver relies on for the
# Polaris. Disabled globally via a NetworkManager conf.d drop-in, applying to every
# Wifi connection (present and future) rather than just the ones this script manages.
POWERSAVE_CONF="/etc/NetworkManager/conf.d/wifi-powersave-off.conf"
if ! grep -q "wifi.powersave" "$POWERSAVE_CONF" 2>/dev/null; then
    sudo mkdir -p "$(dirname "$POWERSAVE_CONF")"
    sudo tee "$POWERSAVE_CONF" > /dev/null <<EOF
[connection]
wifi.powersave = 2
EOF
    echo "Wrote $POWERSAVE_CONF (wifi.powersave = 2, disabled) -- restarting NetworkManager to apply."
    # Restarting NetworkManager briefly drops every active connection, possibly
    # including the SSH session running this script -- same reasoning as the netplan
    # migration above, so it runs the same way (detached, surviving that drop).
    sudo systemd-run --unit="alpaca-nm-restart-$$" --collect -- systemctl restart NetworkManager
else
    echo "$POWERSAVE_CONF already configured -- skipping."
fi

SERVICE_FILE="/etc/systemd/system/polaris-driver.service"
echo "==SETUP== 11. Set up [systemd] services to start the Polaris Driver at boot time."

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

echo "==SETUP== 12. Starts the polaris-driver service."
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
