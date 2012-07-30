#!/bin/bash
SEP="-----------------------------------------------------------------"
echo $SEP
if test "${TRYTON_CONF+set}" != set ; then
echo "Loading conf file"
echo $SEP
. ./scripts.conf
fi
echo "Restarting trytond server"
echo $SEP
$TRYTOND_PATH/trytond -c $TRYTOND_CONF &
echo "Starting tryton client"
echo $SEP
env UBUNTU_MENUPROXY= $TRYTON_PATH/tryton -c $TRYTON_CONF &
sleep 2
echo $SEP
echo "Client ready"
echo $SEP
