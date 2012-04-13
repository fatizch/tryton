#!/bin/bash
SCRIPT=`readlink -f $0`
SCRIPTPATH=`dirname $SCRIPT`
PREV_WD=`readlink -f .`
VE=`echo $VIRTUAL_ENV`
if [ -z $VE ]; then
   source bin/activate
fi
cd tryton-workspace/conf
. ./scripts.conf
cd ../coopbusiness/scripts
SCRIPT_NAME=$1
while getopts ":rckldsh" opt; do
   case $opt in
      r)
         SCRIPT_NAME=resetdb ;;
      c)
         SCRIPT_NAME=cleanandrelaunch ;;
      k)
         SCRIPT_NAME=killtryton ;;
      l)
         SCRIPT_NAME=launch ;;
      d)
         SCRIPT_NAME=updatedatabase ;;
      s)
	 SCRIPT_NAME=sync_coop ;;
      h)
         echo "
-r reset 
-c cleanandrelaunch 
-k killtryton 
-l launch 
-d updatedatabase
-s sync_coop" ;;
      \?)
         echo "Invalid Option" ;;
   esac
done
if [ ! -e "$SCRIPT_NAME" ]; then
   if [ ! -e "$SCRIPT_NAME.sh" ]; then
      echo "Le script '$SCRIPT_NAME' n'existe pas"
   else
      ./$SCRIPT_NAME.sh
   fi
else
   ./$SCRIPT_NAME
fi
cd $PREV_WD
