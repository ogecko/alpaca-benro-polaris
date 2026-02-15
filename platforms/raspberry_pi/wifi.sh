#!/bin/bash
set -e

# polaris-wifi.sh — systemd-based Polaris Wi-Fi setup

INTERFACE="${1:-wlan1}"
SSID="$2"

if [ -z "$SSID" ]; then
    echo "Usage: $0 <interface> <SSID>"
    echo "Example: $0 wlan1 polaris_3b3906"
    exit 1
fi

echo "== Polaris Wi-Fi Setup (NetworkManager method) =="
echo "Interface: $INTERFACE"
echo "SSID: $SSID"

# Ensure interface exists
if ! nmcli device status | grep -q "$INTERFACE"; then
    echo "Interface $INTERFACE not found."
    exit 1
fi

# Delete old connection if it exists
nmcli connection delete polaris 2>/dev/null || true

# Create open network connection with static IP
nmcli connection add \
    type wifi \
    ifname "$INTERFACE" \
    con-name polaris \
    ssid "$SSID" \
    wifi-sec.key-mgmt none \
    ipv4.method manual \
    ipv4.addresses 192.168.0.100/24 \
    ipv4.gateway 192.168.0.1 \
    connection.autoconnect yes

nmcli connection up polaris

echo "== Setup complete =="