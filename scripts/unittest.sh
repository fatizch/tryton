#!/bin/bash
if test "${DATABASE_NAME+set}" != set ; then
   . ./scripts.conf
fi
if test -z $1 ; then
    echo "Test all modules"
    echo ""
    $VIRTUAL_ENV/bin/python $VIRTUAL_ENV/tryton-workspace/coopbusiness/scripts/python_scripts/launch_tryton_script.py $VIRTUAL_ENV/tryton-workspace/coopbusiness/test_case/launch_all_tests.py
else
    echo ""
    echo "Testing module $1"
    echo ""
    $VIRTUAL_ENV/bin/python $VIRTUAL_ENV/tryton-workspace/coopbusiness/scripts/python_scripts/launch_tryton_script.py $VIRTUAL_ENV/tryton-workspace/coopbusiness/modules/$1/tests/test_module.py
fi

