#!/bin/sh

IFACE=`ip route | grep "default" | sed -nr 's/.*dev ([^\ ]+).*/\1/p'`
SCRIPT=`readlink -f "$0"`
SCRIPTPATH=`dirname "$SCRIPT"`
SKABEN_ROOT_DIR=`dirname "$SCRIPTPATH"`
CONF_DIR="$SKABEN_ROOT_DIR/conf"


sed -e "s/\${iface}/'$IFACE'/" \
    -e "s+\${dirpath}+$SKABEN_ROOT_DIR+" "templates/system.yml.template" > "$CONF_DIR/system.yml"
touch "$CONF_DIR/device.yml"  # create empty device config
