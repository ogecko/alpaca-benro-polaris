#!/bin/bash -e
#
# This bootstraps the unified application on a Raspberry Pi.
#
BRANCH="${1:-main}"   # Use first argument as branch name, default to 'main'
REPO_DIR="alpaca-benro-polaris"
REPO_URL="https://github.com/ogecko/alpaca-benro-polaris.git"



echo "==SETUP== Alpaca Benro Polaris Raspberry Pi Setup ======================================."

echo "==SETUP== 1. Update the software on the system, and install dependencies needed for git."
for pkg in git python3-pip python3-numpy python3-scipy; do
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

echo "==SETUP== 3. Create a pyenv and add to ~/.bashrc."
sudo apt-get install python3-venv 
if [ ! -d "$src_home/pyenv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$src_home/pyenv" --system-site-packages
else
    echo "Python venv already exists — skipping creation."
fi
if ! grep -q "alpaca-benro-polaris edits" ~/.bashrc; then
    echo "Adding venv auto-activation to ~/.bashrc..."
    cat <<_EOF >> ~/.bashrc

# start of alpaca-benro-polaris edits
if [ -d "$src_home/pyenv" ]; then
    source "$src_home/pyenv/bin/activate"
    cd "$src_home"
fi
# end of alpaca-benro-polaris edits

_EOF
else
    echo "~/.bashrc already contains venv activation — skipping."
fi
source "$src_home/pyenv/bin/activate"

echo "==SETUP== 4. Install the python dependencies needed for the application."
cd "$src_home/platforms/raspberry_pi"
pip install -r requirements.txt -c constraints.txt



# 0. Update Alpaca Pilot port in config.toml
echo "==SETUP== 6.Updating config.toml with 'alpaca_pilot_port = 8080' =="
sudo sed -i 's/^alpaca_pilot_port = 80 .*/alpaca_pilot_port = 8080/' "$src_home/driver/config.toml"


echo "==SETUP== 6. Set up [systemd] services to start the polaris.service at boot time."
cat systemd/polaris.service | sed \
  -e "s|/home/.*/alpaca-benro-polaris|$src_home|g" \
  -e "s|^ExecStart=.*|ExecStart=$src_home/pyenv/bin/python3 $src_home/driver/main.py|" > /tmp/polaris.service
sudo mv /tmp/polaris.service /etc/systemd/system

echo "==SETUP== 7. Starts the service."
sudo systemctl daemon-reload
sudo systemctl enable polaris
sudo systemctl start polaris

cat <<_EOF
|-------------------------------------|
| Alpaca Benro Polaris Setup Complete |
|                                     |
| You can access Alpaca Pilot via:    |
| http://$(hostname):8080             |
|                                     |
|-------------------------------------|
_EOF
