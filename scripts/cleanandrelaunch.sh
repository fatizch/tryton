#!/bin/bash
SEP="-----------------------------------------------------------------"
echo $SEP
echo "Loading conf file"
echo $SEP
. ./scripts.conf
echo "Killing existing processes (if any)"
echo $SEP
. ./killtryton.sh
echo "Reinstalling modules"
echo $SEP
. ./reset.sh
echo "Cleaning up database"
echo $SEP
cp $DATABASE_BACKUP_FOLDER/$DATABASE_NAME.$DATABASE_EXTENSION $DATABASE_FOLDER/$DATABASE_NAME.$DATABASE_EXTENSION
echo "Updating modules"
echo $SEP
. ./updatedatabase.sh
. ./launch.sh
echo "Launch complete"
echo $SEP
