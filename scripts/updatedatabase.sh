#!/bin/bash
if test "${DATABASE_NAME+set}" != set ; then
   . ./scripts.conf
fi
trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_product
trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_contract
