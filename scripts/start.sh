#!/bin/sh
SCRIPT=`readlink -f $0`
SCRIPTPATH=`dirname $SCRIPT`
PREV_WD=`readlink -f .`
cd $SCRIPTPATH
SCRIPT_NAME=$1
while getopts ":rckld" opt; do
   case $opt in
      r)
         SCRIPT_NAME=reset ;;
      c)
         SCRIPT_NAME=cleanandrelaunch ;;
      k)
         SCRIPT_NAME=killtryton ;;
      l)
         SCRIPT_NAME=launch ;;
      d)
         SCRIPT_NAME=updatedatabase ;;
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
