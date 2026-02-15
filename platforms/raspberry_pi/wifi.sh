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

CONFIG_FILE="/etc/wpa_supplicant/wpa_supplicant-${INTERFACE}.conf"
DHCPCD_FILE="/etc/dhcpcd.conf"

echo "== Polaris Wi-Fi Setup (systemd method) =="
echo "Interface: $INTERFACE"
echo "SSID: $SSID"

# 1️⃣ Create dedicated wpa_supplicant config
echo "== Writing $CONFIG_FILE =="

sudo tee "$CONFIG_FILE" > /dev/null <<EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="$SSID"
    key_mgmt=NONE
}
EOF

sudo chmod 600 "$CONFIG_FILE"

# 2️⃣ Enable systemd instance 
echo "== Enabling wpa_supplicant@${INTERFACE} =="

sudo systemctl enable wpa_supplicant@${INTERFACE}
sudo systemctl restart wpa_supplicant@${INTERFACE}

# 3️⃣ Configure static IP safely via dhcpcd (no flushing)
echo "== Configuring static IP for $INTERFACE =="

if ! grep -q "interface ${INTERFACE}" "$DHCPCD_FILE"; then
    sudo tee -a "$DHCPCD_FILE" > /dev/null <<EOF

interface ${INTERFACE}
static ip_address=192.168.0.100/24
nohook wpa_supplicant
EOF
fi

# 4️⃣ Restart dhcpcd cleanly
sudo systemctl restart dhcpcd

echo "== Setup complete =="
echo "Check status:"
echo "  systemctl status wpa_supplicant@${INTERFACE}"
echo "  ip a show ${INTERFACE}"