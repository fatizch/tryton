#!/bin/bash
SEP=------------------------------------------------
EXPECTED_ARGS=2

if [ $# -ne $EXPECTED_ARGS ]
then
        echo $SEP
        echo "Usage: `basename $0` {path} {bitbucket username}"
        echo $SEP
elif [ ! -e "$1" ]
then
        echo $SEP
        echo $1 must be an existing directory
        echo $SEP
else
	. ./get_tryton.sh $1
	. ./get_coop.sh $1 $2
	. ./configure_directory.sh $1
fi
