#!/bin/sh
SCRIPT=`readlink -f $0`
SCRIPTPATH=`dirname $SCRIPT`
PREV_WD=`readlink -f .`
cd $SCRIPTPATH
SCRIPT_NAME=$1
if [ ! -e "$SCRIPT_NAME" ]; then
   if [ ! -e "$SCRIPT_NAME.sh" ]; then
      echo "Le script '$1' n'existe pas"
   else
      ./$SCRIPT_NAME.sh
   fi
else
   ./$SCRIPT_NAME
fi
cd $PREV_WD
