#!/bin/bash
SEP=------------------------------------------------
EXPECTED_ARGS=1
PWD=$( pwd )
if echo $1 | grep '^/' > /dev/null
then
    FINALPWD=$1
else
    FINALPWD=$PWD/$1
fi

if [ $# -ne $EXPECTED_ARGS ]
then
	echo $SEP
     	echo "Usage: `basename $0` {directory}"
	echo $SEP
elif [ ! -e `dirname $1` ]
then
	echo $SEP
	echo `dirname $1` must be an existing directory
	echo $SEP
elif [ -e "$1" ]
then
	echo $SEP
	echo `basename $1` already exists in `dirname $1` !
	echo $SEP
else
	mkdir $1
	echo $SEP
	echo Creating Virtual Env in $1
	echo $SEP
	virtualenv $1
	cd $1
	echo $SEP
	echo Entering Virtual Env
	echo $SEP
	source bin/activate
	echo Installing shared pip packages
	echo $SEP
    # pytz does not install properly through pip
    easy_install pytz
    pip install dateutils
    # pyflakes 0.5.0 for rule_engine validation, to upgrade
    pip install pyparsing==1.5.7 pyflakes==0.5.0
	echo $SEP
	echo Installing server pip packages
	echo $SEP
    # Genshi 0.6 for relatorio compatibility
    pip install lxml polib genshi==0.6 relatorio python-ldap pywebdav vobject pydot ibanlib
	echo $SEP
	echo Installing client packages
	echo $SEP
   # More relinking than installing
    if [ -e "/usr/lib/python2.7/dist-packages/gobject" ]
    then
        # Looks like we found the shared libraries path
        ln -s /usr/lib/python2.7/dist-packages/gtk* $FINALPWD/lib/python2.7/site-packages/
        ln -s /usr/lib/python2.7/dist-packages/pygtk.p* $FINALPWD/lib/python2.7/site-packages/
        ln -s /usr/lib/python2.7/dist-packages/gobject $FINALPWD/lib/python2.7/site-packages/
        ln -s /usr/lib/python2.7/dist-packages/glib $FINALPWD/lib/python2.7/site-packages/
        ln -s /usr/lib/python2.7/dist-packages/cairo $FINALPWD/lib/python2.7/site-packages/
    elif [ -e "/usr/lib64/python2.7/site-packages/gobject" ]
    then
        # 64 bits ! The more the better
        ln -s /usr/lib64/python2.7/site-packages/gtk* $FINALPWD/lib/python2.7/site-packages/
        ln -s /usr/lib64/python2.7/site-packages/pygtk.p* $FINALPWD/lib/python2.7/site-packages/
        ln -s /usr/lib64/python2.7/site-packages/gobject $FINALPWD/lib/python2.7/site-packages/
        ln -s /usr/lib64/python2.7/site-packages/glib $FINALPWD/lib/python2.7/site-packages/
        ln -s /usr/lib64/python2.7/site-packages/cairo $FINALPWD/lib/python2.7/site-packages/
    else
        # Libraries not found
        echo No gtk libraries were found, the client will not be fonctional
    fi
	echo $SEP
	echo Installing Optionnal packages
    echo $SEP
    # Postgres support
    pip install psycopg2
    # Batchs managing
    pip install celery flower
    echo $SEP
	echo Installation complete, remember to add
	echo 	'[extensions]'
	echo	'hgnested='
	echo	'hgreview='
	echo	''
	echo	'[review]'
	echo	'server = http://codereview.tryton.org'
	echo	'send_email = False (True if you are sure of what you are doing)'
	echo to your home hgrc file before calling coopinstall.sh
	echo $SEP
fi
