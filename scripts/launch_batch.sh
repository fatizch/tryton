#!/bin/bash
SEP="-----------------------------------------------------------------"
if [ "$1" = "" ]
then
    echo $SEP
    echo No batch name provided
    echo $SEP
else
    echo $SEP
    echo Killing pending celery instances
    echo $SEP
    ps ax | grep celery | awk '{print $1}' | xargs kill
    echo $SEP
    echo Starting daemon workers
    echo "(Using configuration file $TRYTON_CONF/celeryconfig.py)"
    echo $SEP
    celery multi start CoopBatch -l info --app=trytond.modules.coop_utils.batch_launcher --config=trytond.modules.coop_utils.celeryconfig --logfile=$ENV_FOLDER/tryton-workspace/logs/%n.log
    echo $SEP
    if [ "$2" = "" ]
    then
        echo Starting batch $1
        echo $SEP
        celery call trytond.modules.coop_utils.batch_launcher.generate_all --args=['"'$1'"']
    else
        echo Starting batch $1 at date $2
        echo $SEP
        celery call trytond.modules.coop_utils.batch_launcher.generate_all --args=['"'$1'"','"'$2'"']
    fi
fi

