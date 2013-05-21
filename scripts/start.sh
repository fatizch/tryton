#!/bin/bash
SCRIPT=`readlink -f $0`
SCRIPTPATH=`dirname $SCRIPT`
PREV_WD=`readlink -f .`
VE=`echo $VIRTUAL_ENV`
if [ -z $VE ]; then
   source bin/activate
fi
cd $VIRTUAL_ENV
cd tryton-workspace/conf
. ./scripts.conf
cd ../coopbusiness/scripts
SCRIPT_NAME=$1
while getopts ":bdehklprstu" opt; do
   case $opt in
        b)
            SCRIPT_NAME=launch_batch ;;
        d)
            SCRIPT_NAME=updatedatabase  ;;
        e)
            SCRIPT_NAME=export_translations  ;;
        h)
            echo "
-b launch_batch
-d updatedatabase
-e export_translations
-k killtryton 
-l launch 
-r reset 
-s sync_coop
-t test_case
-u unittest" ;;
        k)
            SCRIPT_NAME=killtryton  ;;
        l)
            SCRIPT_NAME=launch  ;;
        p)
            SCRIPT_NAME=print_status ;;
        r)
            SCRIPT_NAME=resetdb ;;
        s)
            SCRIPT_NAME=sync_coop  ;;
        t)
            SCRIPT_NAME=test_case  ;;
        u)
            SCRIPT_NAME=unittest  ;;
        \?)
            echo "Invalid Option" ;;
   esac
done
if [ ! -e "$SCRIPT_NAME" ]; then
   if [ ! -e "$SCRIPT_NAME.sh" ]; then
      echo "Le script '$SCRIPT_NAME' n'existe pas"
   else
        shift
        ./$SCRIPT_NAME.sh "$@"
   fi
else
    shift
    ./$SCRIPT_NAME "$@"
fi
cd $PREV_WD
