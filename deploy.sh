#!/usr/bin/env bash

PYVER='3.7'
trap "exit" INT

help () 
{
  echo "Usage: deploy.sh [install|reset]"
  exit
}

if [[ -z $1 ]]; then
  help
fi

# systemd

service () {
  path=$(pwd)
  sed -e "s/\${script_path}/$path/" "template.service" \
      > "newlock.service"
}

check_uname () {
  if ! [ "$(grep -Ei 'debian|buntu|mint' /etc/*release)" ]; then
    echo -e " > Sorry, only Debian-based distros supported for auto-deploy\n"\
    "> manual process:\n"\
    "   sqlite3 python3.7 python3.7-venv should be installed\n"\
    "   python3.7 -m venv venv\n"\
    "   source ./venv/bin/activate\n"\
    "   pip install --upgrade pip\n"\
    "   pip install -r requirements.txt\n"\
    "   ./deploy.sh reset\n"
    exit
  fi
}

# deploy

deploy () {

  SQLITE=""
  PYTHON=""
  PYTHON_VENV="python$PYVER-venv"
   
  PKG_OK=$(dpkg-query -W --showformat='${Status}\n' sqlite3|grep "install ok installed") 
 
  if [[ "$PKG_OK" == "" ]]; then
    SQLITE="sqlite3"
  fi
 
  subver=$(python3 -c 'import sys; print(sys.version_info[1])')
  
  if [[ $((subver + 1)) != 7 ]]; then
    echo '[!] application require python'$PYVER
    echo '[!] your version is:' $(python3 --version)
    echo -e "trying to install python"$PYVER
    PYTHON="python$PYVER"
  fi

  sudo apt-get install -y --no-install-recommends $SQLITE $PYTHON $PYTHON_VENV

  echo -e "setting up virtual environment"
  if  [ -d "./venv" ]; then 
    rm -rf "venv"
  fi
  python$PYVER -m venv venv
  source "./venv/bin/activate"
  PY=$(which python$PYVER)
  $PY -m pip install --upgrade pip
  pip install -r requirements.txt --no-cache-dir
  # unpacking resources
  if [ -f "./resources.tar.gz" ]; then
    tar xvzf resources.tar.gz
  fi
  echo -e "... done!\n"
  echo -e "\n  --------"
  echo -e "  How to autostart with systemd:\n"\
          " cp newlock.service /etc/systemd/system/\n"\
          " systemctl daemon-reset\n"\
          " systemctl enable newlock"
  echo -e "  --------\n"

}

# reset

reset () 
{
  echo -e "[>] resetting __ LOCK __ device configuration"
  if [ -f "./local.db" ]; then
    rm -f "./local.db"
  fi
  sqlite3 "local.db" < ./cfg/lock.sql
  touch ./ts "local.log"
  iface=$(ip route | grep "default" | sed -nr 's/.*dev ([^\ ]+).*/\1/p')
  sed -e "s/\${iface}/'$iface'/" "cfg/config_template.yml" > "config_running.yml"
  echo "[>] done!"
}

# main routine

if [ "$1" = 'install' ]; then
  check_uname
  deploy
  reset 
elif [ "$1" = 'reset' ]; then
  reset 
else
  help
fi
