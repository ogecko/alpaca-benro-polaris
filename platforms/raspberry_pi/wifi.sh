#!/bin/bash
set -e

# wifi.sh — Setup Polaris Wi-Fi auto-connect on wlxe4fac4e6dea5

INTERFACE="wlxe4fac4e6dea5"
SSID="polaris_3b3906"

CONFIG_FILE="/etc/wpa_supplicant/wpa_supplicant-polaris.conf"
SERVICE_FILE="/etc/systemd/system/polaris-wifi.service"

echo "== Polaris Wi-Fi Setup =="

# 0. Update Alpaca Pilot port in config.toml
echo "== Updating config.toml with 'alpaca_pilot_port = 8080' =="
sudo sed -i 's/^alpaca_pilot_port = 80 .*/alpaca_pilot_port = 8080/' ../../driver/config.toml

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

[Service]
Type=simple
ExecStart=/sbin/wpa_supplicant -i $INTERFACE -c $CONFIG_FILE -D nl80211
ExecStartPost=/sbin/dhclient $INTERFACE
Restart=always
RestartSec=5

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
