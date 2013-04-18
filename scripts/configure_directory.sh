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
	cd bin
	ln -s ../tryton-workspace/coopbusiness/scripts/start.sh coop_start 2> /dev/null
	cd ..
	echo $SEP
	echo Entering Virtual Env
	echo $SEP
	source bin/activate
	echo $SEP
	echo Creating links between working directory and tryton modules
	echo $SEP
	cd tryton-workspace/trytond/trytond/modules
    find . -maxdepth 1 -type l | xargs rm
    ln -s ../../../coopbusiness/modules/* . 2> /dev/null
	cd ../../../..
	ln -s tryton-workspace/coopbusiness/scripts/start.sh . 2> /dev/null
	cd tryton-workspace
	echo $SEP
	echo Configuring workspace and scripts, creating minimalist tryton server conf file
    if [ ! -e "logs" ]
    then
        mkdir logs
    fi
    if [ ! -e "conf" ]
    then
        mkdir logs
    fi
	cd conf
    if [ ! -e "scripts.conf" ]
    then
        echo "#!/bin/sh" > scripts.conf
        echo "ENV_FOLDER=$TOPPATH" >> scripts.conf
        echo "DATABASE_FOLDER=\$ENV_FOLDER/tryton-workspace/data" >> scripts.conf
        echo "DATABASE_BACKUP_FOLDER=\$DATABASE_FOLDER/BackUp" >> scripts.conf
        echo "DATABASE_NAME=Test" >> scripts.conf
        echo "DATABASE_EXTENSION=sqlite" >> scripts.conf
        echo "TRYTOND_CONF=\$ENV_FOLDER/tryton-workspace/conf/trytond.conf" >> scripts.conf
        echo "TRYTON_CONF=\$ENV_FOLDER/tryton-workspace/conf/tryton.conf" >> scripts.conf
        echo "REPOS_ROOT=\$ENV_FOLDER/tryton-workspace/" >> scripts.conf
        echo "TRYTOND_PATH=\$ENV_FOLDER/tryton-workspace/trytond/bin" >> scripts.conf
        echo "TRYTON_PATH=\$ENV_FOLDER/tryton-workspace/tryton/bin" >> scripts.conf
        echo "# demo / dev / debug" >> scripts.conf
        echo "TRYTON_LAUNCH_MODE=demo" >> scripts.conf
        echo "export ENV_FOLDER" >> scripts.conf
        echo "export DATABASE_FOLDER" >> scripts.conf
        echo "export DATABASE_BACKUP_FOLDER" >> scripts.conf
        echo "export DATABASE_NAME" >> scripts.conf
        echo "export DATABASE_EXTENSION" >> scripts.conf
        echo "export TRYTOND_CONF" >> scripts.conf
        echo "export TRYTON_CONF" >> scripts.conf
        echo "export REPOS_ROOT" >> scripts.conf
        echo "export TRYTOND_PATH" >> scripts.conf
        echo "export TRYTON_PATH" >> scripts.conf
        echo "export TRYTON_LAUNCH_MODE" >> scripts.conf
    fi
    if [ ! -e "trytond.conf" ]
    then
        echo "[options]" > trytond.conf
        echo "jsonrpc = localhost:8000" >> trytond.conf
        echo "# db_type = sqlite" >> trytond.conf
        echo "db_type = postgresql" >> trytond.conf
        echo "# db_user = tryton" >> trytond.conf
        echo "# db_password = tryton" >> trytond.conf
        echo "data_path = $TOPPATH/tryton-workspace/data" >> trytond.conf
        echo "logfile = $TOPPATH/tryton-workspace/logs/server_logs.log" >> trytond.conf
    fi
    if [ ! -e "celeryconfig.py" ]
    then
        echo "# Rabbit MQ (or other queue managing server) listener" > celeryconfig.py
        echo "BROKER_URL = 'amqp://guest:guest@localhost:5672//'" >> celeryconfig.py
        echo "" >> celeryconfig.py
        echo "# Number of threads per worker" >> celeryconfig.py
        echo "CELERYD_CONCURRENCY = 4" >> celeryconfig.py
        echo "" >> celeryconfig.py
        echo "# Should "prints" be included in the log ?" >> celeryconfig.py
        echo "CELERY_REDIRECT_STDOUT = False" >> celeryconfig.py
        echo "" >> celeryconfig.py
        echo "# Task log formatting" >> celeryconfig.py
        echo "CELERYD_TASK_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s]' + \\" >> celeryconfig.py
        echo "    '[%(task_name)s] %(message)s'" >> celeryconfig.py
        echo "" >> celeryconfig.py
        echo "# Tryton db name" >> celeryconfig.py
        echo "TRYTON_DATABASE = 'new_feature'" >> celeryconfig.py
        echo "" >> celeryconfig.py
        echo "# Trytond config filepath" >> celeryconfig.py
        echo "TRYTON_CONFIG = '$TOPPATH/tryton-workspace/conf/trytond.conf'" >> celeryconfig.py
    fi
    if [ ! -e "tryton.conf" ]
    then
        cp coopbusiness/defaults/tryton.conf .
    fi
	cd ../../lib/python2.7/site-packages
    if [ ! -e '_trytond_path.pth' ]
    then
        echo "import sys; sys.__plen = len(sys.path)" > _trytond_path.pth
        echo "$TOPPATH/tryton-workspace/trytond" >> _trytond_path.pth
        echo "import sys; new=sys.path[sys.__plen:]" >> _trytond_path.pth
        echo "del sys.path[sys.__plen:]" >> _trytond_path.pth
        echo "p=getattr(sys,'__egginsert',0)" >> _trytond_path.pth
        echo "sys.path[p:p]=new" >> _trytond_path.pth
        echo "sys.__egginsert = p+len(new)" >> _trytond_path.pth
    fi
    if [ ! -e '_tryton_path.pth' ]
    then
        echo "import sys; sys.__plen = len(sys.path)" > _tryton_path.pth
        echo "$TOPPATH/tryton-workspace/tryton" >> _tryton_path.pth
        echo "import sys; new=sys.path[sys.__plen:]" >> _tryton_path.pth
        echo "del sys.path[sys.__plen:]" >> _tryton_path.pth
        echo "p=getattr(sys,'__egginsert',0)" >> _tryton_path.pth
        echo "sys.path[p:p]=new" >> _tryton_path.pth
        echo "sys.__egginsert = p+len(new)" >> _tryton_path.pth
    fi
    if [ ! -e '_proteus_path.pth' ]
    then
        echo "import sys; sys.__plen = len(sys.path)" > _proteus_path.pth
        echo "$TOPPATH/tryton-workspace/proteus" >> _proteus_path.pth
        echo "import sys; new=sys.path[sys.__plen:]" >> _proteus_path.pth
        echo "del sys.path[sys.__plen:]" >> _proteus_path.pth
        echo "p=getattr(sys,'__egginsert',0)" >> _proteus_path.pth
        echo "sys.path[p:p]=new" >> _proteus_path.pth
        echo "sys.__egginsert = p+len(new)" >> _proteus_path.pth
    fi
    if [ ! -e '_celery_conf_path.pth' ]
    then
        echo "import sys; sys.__plen = len(sys.path)" > _celery_conf_path.pth
        echo "$TOPPATH/tryton-workspace/conf" >> _celery_conf_path.pth
        echo "import sys; new=sys.path[sys.__plen:]" >> _celery_conf_path.pth
        echo "del sys.path[sys.__plen:]" >> _celery_conf_path.pth
        echo "p=getattr(sys,'__egginsert',0)" >> _celery_conf_path.pth
        echo "sys.path[p:p]=new" >> _celery_conf_path.pth
        echo "sys.__egginsert = p+len(new)" >> _celery_conf_path.pth
    fi
    if [ ! -e '_trytond_celery_path.pth' ]
    then
        echo "import sys; sys.__plen = len(sys.path)" > _trytond_celery_path.pth
        echo "$TOPPATH/tryton-workspace/coopbusiness/trytond_celery" >> _trytond_celery_path.pth
        echo "import sys; new=sys.path[sys.__plen:]" >> _trytond_celery_path.pth
        echo "del sys.path[sys.__plen:]" >> _trytond_celery_path.pth
        echo "p=getattr(sys,'__egginsert',0)" >> _trytond_celery_path.pth
        echo "sys.path[p:p]=new" >> _trytond_celery_path.pth
        echo "sys.__egginsert = p+len(new)" >> _trytond_celery_path.pth
    fi
	echo $SEP
	echo Done
	echo $SEP
fi
