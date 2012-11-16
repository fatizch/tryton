#!/bin/bash
PREV_WD=`readlink -f .`
VE=`echo $VIRTUAL_ENV`
if [ -z $VE ]; then
   source bin/activate
fi
while getopts ":hft" opt; do
   case $opt in
      f)
         FILE_KIND=form.rng ;;
      t)
         FILE_KIND=tree.rng ;;
      h)
         echo "
-f form 
-t tree" ;;
      \?)
         echo "Invalid Option" ;;
   esac
done
if [ $FILE_KIND ]; then
   xmllint  --relaxng $VIRTUAL_ENV/tryton-workspace/trytond/trytond/ir/ui/$FILE_KIND $2
else
   echo "Missing option"
fi
cd $PREV_WD
