#!/bin/bash
if test "${DATABASE_NAME+set}" != set ; then
   . ./scripts.conf
fi
$TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u coop_utils
$TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_product
$TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_party
$TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_process
$TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_contract
$TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_collective
