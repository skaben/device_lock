#!/bin/sh

SCRIPT=`readlink -f "$0"`
SCRIPTPATH=`dirname "$SCRIPT"`
SKABEN_ROOT_DIR=`dirname "$SCRIPTPATH"`
SERVICE_FILE="$SKABEN_ROOT_DIR/skabenlock.service.tmp"

touch $SERVICE_FILE
sed -e "s+\${dirpath}+$SKABEN_ROOT_DIR+" "$SKABEN_ROOT_DIR/templates/lock.service.template" >$SERVICE_FILE
cp $SERVICE_FILE /etc/systemd/system/skabenlock.service

systemctl daemon-reload
systemctl disable newlock &> /dev/null
systemctl enable skabenlock
systemctl start skabenlock