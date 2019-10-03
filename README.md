# Coog - The open source insurance software

## Installation

Note: This is intended for a quick development environment creation. For
deployment, you should use [docker](https://github.com/coopengo/coog-admin/) /
[kubernetes](https://github.com/coopengo/kubernetes/tree/k8s) tooling

For more complete installation instructions, checkout the [appropriate wiki
page](https://github.com/coopengo/coog/wiki/dev-start)

### Prerequisites

All commands assume you are using a recent debian based system (Debian >= 9 /
Ubuntu >= 18.04)

You should have a user on github which has access to the coog repositories, and
a working internet connection.

### System Requirements

```bash
sudo apt-get install postgresql postgresql-contrib redis-server \
    python-gi-cairo libgtksourceview-3.0-1 gir1.2-gtksource-3.0 \
    libcairo2-dev libgirepository1.0-dev libsqlite3-dev python3-pip \
    python3-virtualenv
```

### Postgres configuration

```bash
# Create a privileged user for database management
sudo su postgres -c 'psql -c "CREATE ROLE tryton WITH SUPERUSER"'

# Add a password
sudo su postgres -c "psql -c \"ALTER ROLE tryton WITH PASSWORD 'tryton'\""

# Force database connections to authenticate using md5
sudo sed -i 's/\(local\s*all\s*all\s*\)peer/\1md5/' \
    /etc/postgresql/*/main/pg_hba.conf

# Restart the service
sudo service postgresql restart
```

### Create a working environment

```bash
# Create a working folder
mkdir ~/coog && cd ~/coog

# Setup a virtual environment
virtualenv -p python3 coog

# Activate it
source bin/activate

# Upgrade python package installer
pip install --upgrade pip

# Clone the repositories (switch "git@github.com:" with "https://github.com/"
# if you do not have a ssh key configured in github):
git clone git@github.com:coopengo/tryton.git
git clone git@github.com:coopengo/trytond.git
git clone git@github.com:coopengo/trytond-modules.git
git clone git@github.com:coopengo/proteus.git
git clone git@github.com:coopengo/sao.git
git clone git@github.com:coopengo/coog.git

# Optionnaly clone the customer repository
git clone git@github.com:coopengo/customers.git

# Create a configuration folder
mkdir conf

# Create symlinks in virtualenv file
./coog/bin/coog init bin

# Install python dependencies
coog dep

# Init default configuration
coog conf

# Link modules
coog repo link

# Use our "tryton" db user in the configuration
sed -i "s/\(uri = .*\)postgres:postgres/\1tryton:tryton/" conf/trytond.conf
```

## Setup a Database

The manual way:

```bash
# Create the database
sudo su postgres -c "createdb coog"

# Register it as a tryton database (input admin user / email when required)
coog module update

# Then you got an empty database in which you can manually activate modules as
# needed
```

## Coog command cheat sheet

**Warning: All commands should be executed in an activated virtual
environment**

### Setup

Refresh python dependencies:

```bash
coog dep
```

Make the server aware of newly created / deleted modules:

```bash
coog repo link
```

### Classics

Update the server:

```bash
coog module update
```

Register and activate a new module (after a ``coog repo link``):

```bash
coog module update ir <my_module_name>
```

Start / Stop / Kill the server:

```bash
coog server start / stop / kill
```

Start / Stop / Kill the client:

```bash
coog client start / stop / kill
```

### Batches

Start celery workers:

```bash
coog celery start 2
```

Exec a batch:

```bash
coog batch exec <batch_name> <params>
```

Check tasks of a batch:

```bash
coog batch query qlist <batch_name>
```

Check failed tasks of a batch:

```bash
coog batch query qlist <batch_name> fail
```

Check failed tasks of **ALL** batches:

```bash
coog batch query flist
```

Check the result of a batch job:

```bash
coog batch query j <job_id>
```

Archive a batch run (backup jobs and results in archive queues):

```bash
coog batch query qarchive <batch_name>
```

Force a job size, forbid splitting:

```bash
coog batch exec <batch_name> <params> --job_size=10 --no-split
```

Look for jobs between two dates:

```bash
# From (strict) 2020-01-01
coog batch query list 2020-01-01

# Up to (strict) 2020-01-01
coog batch query list ~2020-01-01

# Between (strict) 2020-01-01 and 2020-01-31
coog batch query list 2020-01-01~2020-01-31
```
Visualize batch execution:

```bash
# If not already done, install flower
pip install flower

# Start flower (default is on localhost:5555)
coog celery flower
```

