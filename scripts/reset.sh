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
rm -r $ENV_FOLDER/lib/python2.7/site-packages/coop_*
echo $SEP
echo "Reinstalling coop utils"
echo $SEP
easy_install -UZ $REPOS_ROOT/coopbusiness/coop_utils
echo $SEP
echo "Reinstalling party"
echo $SEP
easy_install -UZ $REPOS_ROOT/coopbusiness/insurance_party
echo $SEP
echo "Reinstalling product"
echo $SEP
easy_install -UZ $REPOS_ROOT/coopbusiness/insurance_product
echo $SEP
echo "Reinstalling contract"
echo $SEP
easy_install -UZ $REPOS_ROOT/coopbusiness/insurance_contract
echo $SEP

