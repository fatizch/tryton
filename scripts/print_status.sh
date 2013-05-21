SEP=------------------------------------------------------
cd $ENV_FOLDER/tryton-workspace
echo $SEP
echo Coopbusiness Status
echo $SEP
cd coopbusiness
hg st
echo $SEP
echo Trytond Status
echo $SEP
cd ../trytond
hg st
echo $SEP
echo Tryton Status
echo $SEP
cd ../tryton
hg st
