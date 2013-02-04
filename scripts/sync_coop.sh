#!/bin/bash
cd $ENV_FOLDER/tryton-workspace/coopbusiness
hg pull -u -b default
cd $ENV_FOLDER/tryton-workspace/tryton
hg pull -u
cd $ENV_FOLDER/tryton-workspace/trytond
hg pull -u
cd $ENV_FOLDER/tryton-workspace/proteus
hg pull -u
cd $ENV_FOLDER/tryton-workspace/trytond/trytond/modules
ln -s ../../../coopbusiness/* . 2> /dev/null
rm defaults scripts test_case
