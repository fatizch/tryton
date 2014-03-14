#!/bin/bash
SEP=------------------------------------------------
EXPECTED_ARGS=3

if [ $# -ne $EXPECTED_ARGS ]
then
        echo $SEP
        echo "Usage: `basename $0` {path} {bitbucket username} {bitbucket
        email}"
else
	cd $1
	echo $SEP
	echo Entering Virtual Env
	echo $SEP
	source bin/activate
	echo $SEP
	cd tryton-workspace
	echo $SEP
	echo Cleaning previous installation
	echo $SEP
	rm -r coopbusiness
	echo $SEP
	echo Getting Coop modules
	echo $SEP
	hg clone https://$3@bitbucket.org/$2/coopbusiness -r default
	echo $SEP
	echo Done
	echo $SEP
fi
