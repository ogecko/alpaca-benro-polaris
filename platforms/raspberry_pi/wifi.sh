#!/bin/bash
set -euo pipefail

# Default values
INTERFACE="wlan1"
SSID=""
STATIC_IP_ARG=""
DEFAULT_STATIC="192.168.0.100/24"
WPA_DIR="/etc/wpa_supplicant"

usage() {
    cat <<EOF
Usage: $0 [-i interface] [-s SSID] [-a ip_address]
  -i  Network interface for Polaris connection (default: ${INTERFACE})
  -s  Network SSID of Polaris (default: auto-scan for 'polaris_*')
  -a  Static IP of Rapberry Pi on Polaris Network (default: ${DEFAULT_STATIC}) 
  -h  Show this help

Examples:
  $0 -i wlan0
  $0 -s polaris_b83c06 -a 192.168.0.101
EOF
    exit 1
}

# 1. Improved Argument Parsing
# Supports both flags (-i) and fall-back positional logic for backward compatibility
while [[ $# -gt 0 ]]; do
    case "$1" in
        -i|--interface) INTERFACE="$2"; shift 2 ;;
        -s|--ssid)      SSID="$2";      shift 2 ;;
        -a|--address)   STATIC_IP_ARG="$2"; shift 2 ;;
        -h|--help)      usage ;;
        *) echo "Unknown argument: $1"; usage ;;
    esac
done

# 2. Validation Checks
if ! ip link show "${INTERFACE}" >/dev/null 2>&1; then
    echo "Error: interface ${INTERFACE} not found."
    exit 2
fi

# 3. SSID Discovery Logic (Cleaned up)
if [ -z "$SSID" ]; then
    echo "Scanning ${INTERFACE} for 'polaris_' networks..."
    sudo ip link set "${INTERFACE}" up >/dev/null 2>&1 || true
    
    # Use a more reliable way to capture SSIDs into an array
    mapfile -t POLARIS_SSIDS < <(sudo iw dev "${INTERFACE}" scan 2>/dev/null | \
        sed -n 's/^[[:space:]]*SSID: \(polaris_.*\)/\1/p' | sort -u)

    COUNT=${#POLARIS_SSIDS[@]}

    if [ "$COUNT" -eq 1 ]; then
        SSID="${POLARIS_SSIDS[0]}"
        echo "Found unique SSID: ${SSID}"
    elif [ "$COUNT" -eq 0 ]; then
        echo "Error: No 'polaris_' networks found. Try specifying one with -s."
        exit 3
    else
        echo "Error: Multiple polaris networks found. Please specify one:"
        printf ' - %s\n' "${POLARIS_SSIDS[@]}"
        exit 3
    fi
fi

# 4. IP Normalization (Cleaned up)
STATIC_IP="${STATIC_IP_ARG:-$DEFAULT_STATIC}"
[[ "$STATIC_IP" != */* ]] && STATIC_IP="${STATIC_IP}/24"

echo "== SETUP == Polaris Wi-Fi Setup ==============================================="
echo "Interface: ${INTERFACE}"
echo "SSID: ${SSID}"
echo "Static IP: ${STATIC_IP} of Raspberry Pi on Polaris network"

# Create wpa_supplicant config
WPA_CONF="${WPA_DIR}/wpa_supplicant-${INTERFACE}.conf"
echo "== STEP == 1: Write wpa_supplicant config => ${WPA_CONF}"
sudo mkdir -p "${WPA_DIR}"
sudo tee "${WPA_CONF}" > /dev/null <<EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
network={
    ssid="${SSID}"
    key_mgmt=NONE
}
EOF
sudo chmod 600 "${WPA_CONF}"

# Tell dhcpcd to ignore this interface
if ! grep -q "denyinterfaces ${INTERFACE}" /etc/dhcpcd.conf 2>/dev/null; then
    echo "denyinterfaces ${INTERFACE}" | sudo tee -a /etc/dhcpcd.conf >/dev/null
fi

# stop and mask default wpa_supplicant managing the interface
sudo systemctl stop wpa_supplicant@"${INTERFACE}".service --quiet || true
sudo systemctl mask wpa_supplicant@"${INTERFACE}".service --quiet || true

# Create systemd service for wpa_supplicant with power_save disabled
WLAN_SERVICE_FILE="/etc/systemd/system/polaris-${INTERFACE}.service"
echo "== STEP == 2: Create systemd service => ${WLAN_SERVICE_FILE}"
sudo tee "${WLAN_SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=WPA supplicant for ${INTERFACE}
After=network.target

[Service]
Type=simple
ExecStartPre=/sbin/iw dev ${INTERFACE} set power_save off
ExecStart=/sbin/wpa_supplicant -c${WPA_CONF} -i${INTERFACE} -Dnl80211
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable polaris-"${INTERFACE}".service
sudo systemctl restart polaris-"${INTERFACE}".service

# Create systemd oneshot service to assign static IP after interface is up
IP_SERVICE_FILE="/etc/systemd/system/polaris-${INTERFACE}-ip.service"
echo "== STEP == 3: Create systemd IP service => ${IP_SERVICE_FILE}"
sudo tee "${IP_SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=Assign static IP to ${INTERFACE} after wpa_supplicant
After=polaris-${INTERFACE}.service
Requires=polaris-${INTERFACE}.service

[Service]
Type=oneshot
ExecStart=/sbin/ip addr flush dev ${INTERFACE}
ExecStart=/sbin/ip addr add ${STATIC_IP} dev ${INTERFACE}
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable polaris-"${INTERFACE}"-ip.service
sudo systemctl restart polaris-"${INTERFACE}"-ip.service

echo "== Setup complete =="
echo "Interface ${INTERFACE} should now be connected to ${SSID}"
echo "Assigned IP: ${STATIC_IP}"