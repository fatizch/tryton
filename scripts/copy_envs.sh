#!/bin/bash
SEP=------------------------------------------------
EXPECTED_ARGS=2

if [ $# -ne $EXPECTED_ARGS ]
then
        echo $SEP
        echo "Usage: `basename $0` {from directory} {to directory}"
        echo $SEP
elif [ ! -e "$1" ]
then
        echo $SEP
        echo $1 must be an existing directory
        echo $SEP
elif [ ! -e "$2" ]
then
        echo $SEP
        echo $2 must be an existing directory
        echo $SEP
else
	FROM=$(readlink -m $1)
	TO=$(readlink -m $2)
	echo $FROM
	echo $TO
	echo $SEP
	echo Backuping current .hg folders
	echo $SEP
	cd $TO
	mkdir ../Backup_tmp
	cp -r .hg ../Backup_tmp/
	echo $SEP
	echo Copying files
	echo $SEP
	cp -r -f $FROM/* .
	echo Cleaning existing .hg files
	find . -name *.h* | xargs rm -rf {}
	cp -r ../Backup_tmp/.h* .
	rm -rf ../Backup_tmp
	echo Done
fi
