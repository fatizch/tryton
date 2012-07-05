#!/bin/sh
SEP=------------------------------------------------

echo $SEP
echo Installing necessary packages
echo $SEP
sudo yum install python-pip postgresql python-devel gcc libxml2-devel libxslt-devel postgresql-devel openldap-devel cyrus-sasl-devel pygtk2-devel
echo $SEP
echo Installing necessary dependencies
echo $SEP
sudo yum install build-dep python-ldap
echo $SEP
echo Installing virtualenv for multi env management
echo $SEP
sudo pip-python install virtualenv
echo $SEP
echo System ready
echo $SEP
