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
if test "${TRYTON_LAUNCH_MODE+set}" != set
then
    env UBUNTU_MENUPROXY= $TRYTON_PATH/tryton -c $TRYTON_CONF &
elif [ $TRYTON_LAUNCH_MODE = "demo" ]
then
    env UBUNTU_MENUPROXY= $TRYTON_PATH/tryton -c $TRYTON_CONF &
elif [ $TRYTON_LAUNCH_MODE = "dev" ]
then
    env UBUNTU_MENUPROXY= $TRYTON_PATH/tryton -c $TRYTON_CONF -d &
elif [ $TRYTON_LAUNCH_MODE = "debug" ]
then
    env UBUNTU_MENUPROXY= $TRYTON_PATH/tryton -c $TRYTON_CONF -l DEBUG -d -v &
fi
sleep 2
echo $SEP
echo "Client ready"
echo $SEP
