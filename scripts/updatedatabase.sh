#!/bin/bash
if test "${DATABASE_NAME+set}" != set ; then
   . ./scripts.conf
fi
$TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_product
$TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_process
$TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_contract
