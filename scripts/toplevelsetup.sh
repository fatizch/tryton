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
echo Installing necessary packages
echo $SEP
sudo apt-get install python-pip postgresql python-dev gcc libxml2-dev libxslt-dev libpq-dev python-gtksourceview2 libldap2-dev libsasl2-dev libssl-dev rabbitmq-server
echo $SEP
echo Installing necessary dependencies
echo $SEP
sudo apt-get build-dep python-ldap
echo $SEP
echo Installing virtualenv for multi env management
echo $SEP
sudo pip install virtualenv
echo $SEP
echo System ready
echo $SEP
