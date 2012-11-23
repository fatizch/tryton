#!/bin/bash
if test "${DATABASE_NAME+set}" != set ; then
   . ./scripts.conf
fi
$VIRTUAL_ENV/bin/python $VIRTUAL_ENV/tryton-workspace/coopbusiness/scripts/python_scripts/launch_tryton_script.py $VIRTUAL_ENV/tryton-workspace/coopbusiness/test_case/proteus_test_case.py
