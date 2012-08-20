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
	TOPPATH=$PWD
	echo $SEP
	echo Entering Virtual Env
	echo $SEP
	source bin/activate
	echo $SEP
	echo Creating links between working directory and tryton modules
	echo $SEP
	cd tryton-workspace/trytond/trytond/modules
	ln -s ../../../coopbusiness/* .
	rm defaults scripts test_case
	cd ../../../..
	ln -s tryton-workspace/coopbusiness/scripts/start.sh .
	cd tryton-workspace
	echo $SEP
	echo Configuring workspace and scripts, creating minimalist tryton server conf file
	mkdir data
	cd data
	mkdir BackUp
	cd ..
	mkdir conf
	cd conf
	echo "#!/bin/sh" > scripts.conf
	echo "ENV_FOLDER=$TOPPATH" >> scripts.conf
	echo "DATABASE_FOLDER=\$ENV_FOLDER/tryton-workspace/data" >> scripts.conf
	echo "DATABASE_BACKUP_FOLDER=\$DATABASE_FOLDER/BackUp" >> scripts.conf
	echo "DATABASE_NAME=Test" >> scripts.conf
	echo "DATABASE_EXTENSION=sqlite" >> scripts.conf
	echo "TRYTOND_CONF=\$ENV_FOLDER/tryton-workspace/conf/trytond.conf" >> scripts.conf
	echo "REPOS_ROOT=\$ENV_FOLDER/tryton-workspace/" >> scripts.conf
	echo "TRYTOND_PATH=\$ENV_FOLDER/tryton-workspace/trytond/bin" >> scripts.conf
	echo "TRYTON_PATH=\$ENV_FOLDER/tryton-workspace/tryton/bin" >> scripts.conf
	echo "export ENV_FOLDER" >> scripts.conf
	echo "export DATABASE_FOLDER" >> scripts.conf
	echo "export DATABASE_BACKUP_FOLDER" >> scripts.conf
	echo "export DATABASE_NAME" >> scripts.conf
	echo "export DATABASE_EXTENSION" >> scripts.conf
	echo "export TRYTOND_CONF" >> scripts.conf
	echo "export REPOS_ROOT" >> scripts.conf
	echo "export TRYTOND_PATH" >> scripts.conf
	echo "export TRYTON_PATH" >> scripts.conf
	echo "[options]" > trytond.conf
	echo "jsonrpc = localhost:8000" >> trytond.conf
	echo "db_type = sqlite" >> trytond.conf
	echo "data_path = $TOPPATH/tryton-workspace/data" >> trytond.conf
	cd ..
	echo $SEP
	echo Initializing database
	echo $SEP
	cp coopbusiness/defaults/Test.sqlite data/BackUp/
	cp coopbusiness/defaults/Test.sqlite data/
	cp coopbusiness/defaults/tryton.conf conf/
	echo $SEP
	echo Done
	echo $SEP
fi
