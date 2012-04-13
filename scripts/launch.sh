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
$TRYTON_PATH/tryton &
sleep 2
echo $SEP
echo "Client ready"
echo $SEP
