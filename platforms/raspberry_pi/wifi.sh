#!/bin/bash
set -e

# wifi.sh — Setup Polaris Wi-Fi auto-connect

# --- Parse arguments ---
INTERFACE="${1:-wlan1}"  # Default to wlan1 if not provided
SSID="$2"

if [ -z "$SSID" ]; then
    echo "Usage: $0 <interface> <SSID>"
    echo "Example: $0 wlan1 polaris_3b3906"
    exit 1
fi

CONFIG_FILE="/etc/wpa_supplicant/wpa_supplicant-polaris.conf"
SERVICE_FILE="/etc/systemd/system/polaris-wifi.service"

echo "== Polaris Wi-Fi Setup =="
echo "Interface: $INTERFACE"
echo "SSID: $SSID"

# 1. Stop any running wpa_supplicant for this interface
sudo pkill -f "wpa_supplicant.*$INTERFACE" || true
sudo rm -f /var/run/wpa_supplicant/$INTERFACE


# 1. Create wpa_supplicant config
echo "== Writing $CONFIG_FILE =="
sudo tee $CONFIG_FILE > /dev/null <<EOF
ctrl_interface=/var/run/wpa_supplicant
update_config=1

network={
    ssid="$SSID"
    key_mgmt=NONE
}
EOF

# 2. Create systemd service unit
echo "== Writing $SERVICE_FILE =="
sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Connect $INTERFACE to Polaris hotspot
After=network.target
Wants=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/sbin/wpa_supplicant -B -i $INTERFACE -c $CONFIG_FILE -D nl80211
ExecStartPost=/sbin/ip addr flush dev $INTERFACE
ExecStartPost=/sbin/ip addr add 192.168.0.100/24 dev $INTERFACE
ExecStartPost=/sbin/ip link set $INTERFACE up

[Install]
WantedBy=multi-user.target
EOF

# 3. Reload systemd and enable service
echo "== Reloading systemd =="
sudo systemctl daemon-reload
sudo systemctl enable polaris-wifi.service

# 4. Restart service
echo "== Starting polaris-wifi.service =="
sudo systemctl restart polaris-wifi.service

echo "== Setup complete =="
echo "Check status with: sudo systemctl status polaris-wifi.service"
echo "Logs: journalctl -u polaris-wifi.service -f"
