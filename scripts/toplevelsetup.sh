#!/bin/sh
SEP=------------------------------------------------

echo $SEP
echo Installing necessary packages
echo $SEP
sudo apt-get install python-pip postgresql python-dev gcc libxml2-dev libxslt-dev libpq-dev python-gtksourceview2 libldap2-dev libsasl2-dev libssl-dev
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
