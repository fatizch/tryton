#!/bin/sh
SEP=------------------------------------------------

echo $SEP
echo Installing core packages
echo $SEP
sudo yum install -y python python-pip python-devel mercurial
echo $SEP
echo Installing server packages
echo $SEP
sudo yum install -y gcc libxml2-devel libxslt-devel openldap-devel cyrus-sasl-devel
echo $SEP
echo Installing client packages
sudo yum install -y pygtk2-devel
echo $SEP
echo Installing optional dependencies
echo $SEP
# Postgres dependencies
sudo yum install postgresql postgresql-server postgresql-devel
# Batch dependencies
sudo yum install rabbitmq-server
# Rule engine code displayer (client)
sudo yum install pygtksourceview-devel
echo $SEP
echo Installing virtualenv for multi env management
echo $SEP
sudo pip-python install virtualenv
echo $SEP
echo System ready
echo $SEP
