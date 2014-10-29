#!/bin/bash
SEP=------------------------------------------------
EXPECTED_ARGS=1

if [ $# -ne $EXPECTED_ARGS ]
then
        echo $SEP
        echo "Usage: `basename $0` {path}"
elif [ ! -e "$1" ]
then
        echo $SEP
        echo $1 must be an existing directory
        echo $SEP
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
	hg clone ssh://hg@hg.coopengo.com/coopbusiness -r default
    echo $SEP
    echo Done
    echo $SEP
fi
