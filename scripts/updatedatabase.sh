#!/bin/bash
if test "${DATABASE_NAME+set}" != set ; then
   . ./scripts.conf
fi
if test -z $1 ; then
    echo "Update all modules"
    echo ""
    echo "Update module coop_utils"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u coop_utils
    echo ""
    echo "Update module coop_party"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u coop_party
    echo ""
    echo "Update module coop_party_fr"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u coop_party_fr
    echo ""
    echo "Update module insurance_party"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_party
    echo ""
    echo "Update module insurance_party_fr"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_party_fr
    echo ""
    echo "Update module party_bank"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u party_bank
    echo ""
    echo "Update module insurance_product"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_product
    echo ""
    echo "Update module insurance_process"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_process
    echo ""
    echo "Update module insurance_contract"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_contract
    echo ""
    echo "Update module insurance_collective"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u insurance_collective
else
    echo ""
    echo "Update module $1"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u $1
fi
