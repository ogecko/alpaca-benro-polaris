#!/bin/bash -e

src_home=$(cd $(dirname $0)/.. && pwd)


if $(systemctl is-active --quiet polaris); then
  sudo systemctl stop polaris
fi

cd ${src_home}

sudo apt-get update --yes
#sudo apt-get install --yes libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev llvm libncurses5-dev libncursesw5-dev xz-utils tk-dev libgdbm-dev lzma lzma-dev tcl-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev wget curl make build-essential openssl libgl1

# pyenv
if [ ! -e ~/.pyenv ]; then
  curl https://pyenv.run | bash
  cat <<_EOF >> ~/.bashrc
# start alpaca-benro-polaris
export PYENV_ROOT="\$HOME/.pyenv"
[[ -d \$PYENV_ROOT/bin ]] && export PATH="\$PYENV_ROOT/bin:\$PATH"
eval "\$(pyenv init -)"
eval "\$(pyenv virtualenv-init -)"
# end alpaca-benro-polaris
_EOF

  export PYENV_ROOT="$HOME/.pyenv"
  [[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
  eval "$(pyenv init -)"
  eval "$(pyenv virtualenv-init -)"

  pyenv install 3.12.5
  pyenv virtualenv 3.12.5 ssc-3.12.5

  pyenv global ssc-3.12.5

else
  export PYENV_ROOT="$HOME/.pyenv"
  [[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
  eval "$(pyenv init -)"
  eval "$(pyenv virtualenv-init -)"
fi

git pull
pip install -r requirements.txt

cd raspberry_pi

cat systemd/polaris.service | sed \
  -e "s|/home/.*/alpaca-benro-polaris|$src_home|g" \
  -e "s|^ExecStart=.*|ExecStart=$HOME/.pyenv/versions/ssc-3.12.5/bin/python3 $src_home/root_app.py|" > /tmp/polaris.service
sudo chown root:root /tmp/polaris*.service

sudo rm -f /etc/systemd/system/polaris*
sudo mv /tmp/polaris*.service /etc/systemd/system

sudo systemctl daemon-reload

sudo systemctl enable polaris
sudo systemctl start polaris

if ! $(systemctl is-active --quiet polaris); then
  echo "ERROR: polaris service is not running"
  systemctl status polaris
fi

cat <<_EOF
|-------------------------------------|
| alpaca-benro-polaris update complete|
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
