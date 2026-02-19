#!/bin/bash
set -e

# wifi.sh — systemd-based Polaris Wi-Fi setup with static IP

INTERFACE="${1:-wlan1}"
SSID="$2"
STATIC_IP="192.168.0.100/24"

if [ -z "$SSID" ]; then
    echo "Usage: $0 <interface> <SSID>"
    echo "Example: $0 wlan1 polaris_b83c06"
    exit 1
fi

echo "==SETUP== Alpaca Benro Polaris Wifi Setup ======================================."
echo "Interface: $INTERFACE"
echo "SSID: $SSID"

# Create wpa_supplicant config
WPA_CONF="/etc/wpa_supplicant/wpa_supplicant-${INTERFACE}.conf"
echo "== STEP == 1. Create wpa_supplicant config file ${WPA_CONF}"
sudo tee "$WPA_CONF" > /dev/null <<EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
network={
    ssid="$SSID"
    key_mgmt=NONE
}
EOF
sudo chmod 600 "$WPA_CONF"

# Tell dhcpcd to ignore wlan1
if ! grep -q "denyinterfaces ${INTERFACE}" /etc/dhcpcd.conf; then
    echo "denyinterfaces ${INTERFACE}" | sudo tee -a /etc/dhcpcd.conf
fi
# stop and mask default wpa_supplicant managing wlan1
sudo systemctl stop wpa_supplicant@${INTERFACE}.service --quiet
sudo systemctl mask wpa_supplicant@${INTERFACE}.service --quiet

# Create systemd service for wpa_supplicant
WLAN1_SERVICE_FILE="/etc/systemd/system/polaris-${INTERFACE}.service"
echo "== STEP == 2. Create [systemd] service to connect to ${INTERFACE}"
sudo tee "$WLAN1_SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=WPA supplicant for ${INTERFACE}
After=network.target

[Service]
Type=simple
ExecStart=/sbin/wpa_supplicant -c${WPA_CONF} -i${INTERFACE} -Dnl80211
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start service
sudo systemctl daemon-reload
sudo systemctl enable polaris-${INTERFACE}.service
sudo systemctl restart polaris-${INTERFACE}.service

# Create systemd service to assign static IP after interface is up
IP_SERVICE_FILE="/etc/systemd/system/polaris-ip.service"
echo "== STEP == 3. Create [systemd] service to set static IP address on ${INTERFACE}"
sudo tee "$IP_SERVICE_FILE" > /dev/null <<EOF
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
sudo systemctl enable polaris-ip.service
sudo systemctl start polaris-ip.service

echo "== Setup complete =="
echo "Interface ${INTERFACE} should now be connected to ${SSID}"
echo "Assigned IP: ${STATIC_IP}"