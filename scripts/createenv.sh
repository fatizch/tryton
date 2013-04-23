#!/bin/bash
SEP=------------------------------------------------
EXPECTED_ARGS=1

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
	echo Installing pip packages
	echo $SEP
	pip install polib lxml relatorio genshi==0.6 python-dateutil pywebdav vobject python-ldap pytz psycopg2 hgnested hgreview sphinx ibanlib python-stdnum pydot==1.0.28 pyparsing==1.5.6 pyflakes celery flower
	echo $SEP
	echo $SEP
	echo Creating symbol link for dependencies
	echo $SEP
	ln -s /usr/lib/python2.7/dist-packages/gtk* lib/python2.7/site-packages/
	ln -s /usr/lib/python2.7/dist-packages/pygtk.p* lib/python2.7/site-packages/
	ln -s /usr/lib/python2.7/dist-packages/gobject lib/python2.7/site-packages/
	ln -s /usr/lib/python2.7/dist-packages/glib lib/python2.7/site-packages/
	ln -s /usr/lib/python2.7/dist-packages/cairo lib/python2.7/site-packages/
	ln -s /usr/local/lib/python2.7/dist-packages/ibanlib lib/python2.7/site-packages/
	ln -s /usr/local/lib/python2.7/dist-packages/stdnum/ lib/python2.7/site-packages/
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
