#!/bin/bash
SEP="-----------------------------------------------------------------"
if test "${ENV_FOLDER+set}" != set ; then
echo $SEP
echo "Loading conf file"
echo $SEP
. ./scripts.conf
fi
echo "Removing eggs in site-packages"
rm -r $ENV_FOLDER/lib/python2.7/site-packages/insurance_*
echo $SEP
echo "Reinstalling product"
echo $SEP
easy_install -vUZ $REPOS_ROOT/coopbusiness/insurance_product
echo $SEP
echo "Reinstalling contract"
echo $SEP
easy_install -vUZ $REPOS_ROOT/coopbusiness/insurance_contract
echo $SEP

