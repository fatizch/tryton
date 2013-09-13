#!/bin/sh
SEP=------------------------------------------------

if [ ! -e "/etc/apt/sources.list.d/rabbitmq.list" ]
then
    echo $SEP
    echo Adding sources
    echo $SEP
    echo 'deb http://www.rabbitmq.com/debian testing main' >/tmp/rabbitmq.list
    sudo cp /tmp/rabbitmq.list /etc/apt/sources.list.d/
    rm /tmp/rabbitmq.list
    echo $SEP
    echo Updating apt source list
    echo $SEP
    sudo apt-get update
fi
echo $SEP
echo Installing core packages
echo $SEP
sudo apt-get install python python-pip python-devel mercurial
echo $SEP
echo Installing server packages
echo $SEP
sudo apt-get install gcc libxml2-dev libxslt-dev libldap2-dev libsasl2-dev
echo $SEP
echo Installing client packages
sudo apt-get install python-gtk2
echo $SEP
echo Installing optional dependencies
echo $SEP
# Postgres dependencies
sudo apt-get install postgresql postgresql-contrib libpq-dev
# Batch dependencies
sudo apt-get install rabbitmq-server
# Rule engine code displayer (client)
sudo apt-get install python-gtksourceview2
echo $SEP
echo Installing virtualenv for multi env management
echo $SEP
sudo pip-python install virtualenv
echo $SEP
echo System ready
echo $SEP
