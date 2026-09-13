#!/bin/bash -e
#
# This bootstraps the unified application on a Raspberry Pi.
#
BRANCH="${1:-main}"   # Use first argument as branch name, default to 'main'
REPO_DIR="alpaca-benro-polaris"
REPO_URL="https://github.com/ogecko/alpaca-benro-polaris.git"



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


SERVICE_FILE="/etc/systemd/system/polaris-driver.service"
echo "==SETUP== 6. Set up [systemd] services to start the Polaris Driver at boot time."

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

echo "==SETUP== 7. Starts the polaris-driver service."
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
