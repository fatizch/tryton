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
while getopts ":rckldsuht" opt; do
   case $opt in
      r)
         SCRIPT_NAME=resetdb ;;
      k)
         SCRIPT_NAME=killtryton ;;
      l)
         SCRIPT_NAME=launch ;;
      d)
         SCRIPT_NAME=updatedatabase ;;
      s)
         SCRIPT_NAME=sync_coop ;;
      t)
         SCRIPT_NAME=test_case ;;
      u)
         SCRIPT_NAME=unittest ;;
      h)
         echo "
-r reset 
-c cleanandrelaunch 
-k killtryton 
-l launch 
-d updatedatabase
-s sync_coop
-t test_case" ;;
      \?)
         echo "Invalid Option" ;;
   esac
done
if [ ! -e "$SCRIPT_NAME" ]; then
   if [ ! -e "$SCRIPT_NAME.sh" ]; then
      echo "Le script '$SCRIPT_NAME' n'existe pas"
   else
      ./$SCRIPT_NAME.sh $2
   fi
else
   ./$SCRIPT_NAME
fi
cd $PREV_WD
