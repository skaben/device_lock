#!/bin/sh

SCRIPT=`readlink -f "$0"`
SCRIPTPATH=`dirname "$SCRIPT"`
SKABEN_ROOT_DIR=`dirname "$SCRIPTPATH"`

sed -e "s+\${dirpath}+$SKABEN_ROOT_DIR+" "$SKABEN_ROOT_DIR/templates/lock.service.template" > "$SKABEN_ROOT_DIR/skabenlock.service.tmp"
mv $SKABEN_ROOT_DIR/skabenlock.service.tmp /etc/systemd/system/skabenlock.service

systemctl daemon-reload
systemctl disable newlock &> /dev/null
systemctl enable skabenlock
systemctl start skabenlock