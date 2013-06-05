#!/bin/bash
SEP="-----------------------------------------------------------------"
. ./print_status.sh
echo $SEP
read -p "Are you sure you want to sync (y/n) ? " -n 1 -r
if [[ $REPLY =~ ^[Yy]$ ]]
then
    cd $ENV_FOLDER/tryton-workspace/coopbusiness
    hg pull -u
    cd $ENV_FOLDER/tryton-workspace/tryton
    hg pull -u
    cd $ENV_FOLDER/tryton-workspace/trytond
    hg pull -u
    cd $ENV_FOLDER/tryton-workspace/proteus
    hg pull -u
    cd $ENV_FOLDER/tryton-workspace/trytond/trytond/modules
    cd $ENV_FOLDER
    ./tryton-workspace/coopbusiness/scripts/configure_directory.sh $ENV_FOLDER
fi
