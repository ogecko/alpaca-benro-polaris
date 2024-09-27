#!/bin/bash -e
#
# This bootstraps the unified application on a Raspberry Pi.
#
if [ -e alpaca-benro-polaris ] || [ -e ~/alpaca-benro-polaris ]; then
    echo "ERROR: Existing alpaca-benro-polaris directory detected."
    echo "       You should run the raspberry_pi/update.sh script instead."
    exit 255
fi

echo "==SETUP==: 1. Update the software on the system, and install dependencies needed for git."
sudo apt-get update
sudo apt-get install --yes git python3-pip

echo "==SETUP==: 2. Clone the alpaca-benro-polaris software from github."
git clone https://github.com/ogecko/alpaca-benro-polaris.git
cd  alpaca-benro-polaris

src_home=$(pwd)
mkdir -p logs

echo "==SETUP==: 3. Add pyenv to ~/.bashrc and install Python 3.12.5."
curl https://pyenv.run | bash
cat <<_EOF >> ~/.bashrc
# start of alpaca-benro-polaris edits
export PYENV_ROOT="\$HOME/.pyenv"
[[ -d \$PYENV_ROOT/bin ]] && export PATH="\$PYENV_ROOT/bin:\$PATH"
eval "\$(pyenv init -)"
eval "\$(pyenv virtualenv-init -)"
# end of alpaca-benro-polaris edits
_EOF

export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

pyenv install 3.12.5
pyenv virtualenv 3.12.5 ssc-3.12.5
pyenv global ssc-3.12.5

echo "==SETUP== 4. Install the python dependencies needed for the application."
pip install -r requirements.txt

echo "==SETUP== 5. Set up [systemd] services to start the polaris.service at boot time."
cd platformms/raspberry_pi
cat systemd/polaris.service | sed \
  -e "s|/home/.*/alpaca-benro-polaris|$src_home|g" \
  -e "s|^ExecStart=.*|ExecStart=$HOME/.pyenv/versions/ssc-3.12.5/bin/python3 $src_home/root_app.py|" > /tmp/polaris.service
sudo mv /tmp/polaris.service /etc/systemd/system

echo "==SETUP== 6. Starts the service."
sudo systemctl daemon-reload
sudo systemctl enable polaris
sudo systemctl start polaris

cat <<_EOF
|-------------------------------------|
| alpaca-benro-polaris Setup Complete |
|                                     |
| You can access SSC via:             |
| http://$(hostname).local:5432       |
|                                     |
| Device logs can be found in         |
|  ./alpaca-benro-polaris/logs        |
|                                     |
| Systemd logs can be viewed via      |
| journalctl -u polaris               |
|                                     |
| Current status can be viewed via    |
| systemctl status polaris            |
|-------------------------------------|
_EOF
