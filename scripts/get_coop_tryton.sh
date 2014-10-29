#!/bin/bash
SEP=------------------------------------------------
EXPECTED_ARGS=1

if [ $# -ne $EXPECTED_ARGS ]
then
        echo $SEP
        echo "Usage: `basename $0` {path}"
        echo $SEP
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
	mkdir tryton-workspace
	echo $SEP
	echo Cleaning previous installation
	echo $SEP
	rm -r tryton-workspace/trytond
	rm -r tryton-workspace/tryton
	echo $SEP
	echo Getting Trytond
	echo $SEP
	cd tryton-workspace
	hg clone ssh://hg@hg.coopengo.com/trytond
	echo $SEP
	echo Getting Tryton client
	echo $SEP
	hg clone ssh://hg@hg.coopengo.com/tryton
	echo $SEP
	echo Getting Proteus
	echo $SEP
	hg clone http://hg.tryton.org/proteus
	echo $SEP
	echo Done
	echo $SEP
fi
