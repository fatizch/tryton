#!/bin/bash
if test "${DATABASE_NAME+set}" != set ; then
   . ./scripts.conf
fi
if test -z $1 ; then
    echo "Update all modules"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u all
else
    echo ""
    echo "Update module $1"
    echo ""
    $TRYTOND_PATH/trytond -d $DATABASE_NAME -c $TRYTOND_CONF -u $1
fi
