#!/bin/bash
ACTIVATE="/path/to/virtual_env/bin/activate"
COOG="/path/to/coopbusiness"
SERVER="user@machine:/var/www/coverage/"
RUNTESTS="/path/to/trytond/tests/run-tests.py"
POSTGRESQL_PASSWORD="the_password"
source $ACTIVATE
cd $COOG


echo 'Module by module coog coverage report' > myreport.txt
echo '' >> myreport.txt
echo '' >> myreport.txt


coverage erase
echo 'Global coog coverage report' > myglobalreport.txt
echo '' >> myglobalreport.txt
echo $(date) >> myglobalreport.txt
echo '' >> myglobalreport.txt
for module in $(ls modules)
    do echo $module
    env DO_NOT_TEST_CASES=True coverage run -a --source=modules/$module \
        --omit=*__init__*,*tests*,*test_case_data* "$RUNTESTS" -m $module
    for db in $(PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U postgres -l | grep test | cut -f1 -d '|')
        do PGPASSWORD="$POSTGRESQL_PASSWORD" dropdb -U postgres $db
        done
done
coverage report >> myglobalreport.txt
coverage html -d allreports/"$(date +'%Y_%m_%d')"
coverage erase

echo "<!DOCTYPE html>" > allreports/index.html
echo "<html>" >> allreports/index.html
echo "<h1>Coog coverage reports</h1>" >> allreports/index.html

echo "<table border="1">" >> allreports/index.html
for directory in $(ls -c -I *html allreports)
    do echo $directory 
    echo "<tr><td><a href=$directory/index.html>$directory</a></td>" >> allreports/index.html
    echo "<td>" >> allreports/index.html
    COVERAGE=$( grep pc_cov allreports/$directory/index.html | sed -r "s/[^0-9]//g")
    echo $COVERAGE %>> allreports/index.html
    echo "</td>" >> allreports/index.html
    echo "<td><meter min="0" low="50" optimum="100" high="90" max="100" value="$COVERAGE"></meter></td>" >> allreports/index.html
    echo "</tr>" >> allreports/index.html
done
echo "</html>" >> allreports/index.html


scp -r allreports/ "$SERVER"
