#!/bin/bash
SEP=------------------------------------------------
EXPECTED_ARGS=2

if [ $# -ne $EXPECTED_ARGS ]
then
	echo $SEP
     	echo "Usage: `basename $0` {path} {directory}"
	echo $SEP
elif [ ! -e "$1" ]
then
	echo $SEP
	echo $1 must be an existing directory
	echo $SEP
elif [ -e "$1/$2" ]
then
	echo $SEP
	echo $2 already exists in $1 !
	echo $SEP
else
	cd $1
	mkdir $2
	echo $SEP
	echo Creating Virtual Env in $2
	echo $SEP
	virtualenv $2
	cd $2
	echo $SEP
	echo Entering Virtual Env
	echo $SEP
	source bin/activate
	echo Installing pip packages
	echo $SEP
	pip install polib lxml relatorio genshi python-dateutil pywebdav vobject python-ldap pytz psycopg2 hgnested hgreview
	echo $SEP
	echo $SEP
	echo Creating symbol link for dependencies
	echo $SEP
	ln -s /usr/lib/python2.7/dist-packages/gtk* lib/python2.7/site-packages/
	ln -s /usr/lib/python2.7/dist-packages/pygtk.p* lib/python2.7/site-packages/
	ln -s /usr/lib/python2.7/dist-packages/gobject lib/python2.7/site-packages/
	ln -s /usr/lib/python2.7/dist-packages/glib lib/python2.7/site-packages/
	ln -s /usr/lib/python2.7/dist-packages/cairo lib/python2.7/site-packages/
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
