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
#developpement mode
#env UBUNTU_MENUPROXY= $TRYTON_PATH/tryton -c $TRYTON_CONF -d &

#Non developpement mode for demo or production
#env UBUNTU_MENUPROXY= $TRYTON_PATH/tryton -c $TRYTON_CONF &

#Debug Mode
env UBUNTU_MENUPROXY= $TRYTON_PATH/tryton -c $TRYTON_CONF -l DEBUG -d -v &
sleep 2
echo $SEP
echo "Client ready"
echo $SEP
