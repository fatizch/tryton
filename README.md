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
sudo su postgres -c 'psql -c "CREATE USER tryton WITH SUPERUSER"'

# Add a password
sudo su postgres -c "psql -c \"ALTER USER tryton WITH PASSWORD 'tryton'\""

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

# Init git submodules
git -C trytond-modules submodule init
git -C trytond-modules submodule update

# Create a configuration folder
mkdir conf

# Create symlinks in virtualenv file
./coog/bin/coog init bin

# Init default configuration
coog init conf

# Install python dependencies
coog dep

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

The automatic way, which will automatically build a usable database:

```bash
GEN_CREATE_NEW_DB=1 GEN_DB_NAME=coog coog db demo
```

## Setup API related repositories

This should be done if you want to / need to work with either the coog APIs or
the front-end application (Portal).

In the root of your environment (next to the coog / trytond repositories):

```bash
sudo apt install direnv
sudo apt install docker.io   # (version 18.09 minimum)
sudo apt install docker-compose   # (version 1.21 minimum)

docker run --name mongo --restart always -d -p 27017:27017 mongo

curl -s -L https://git.io/n-install | bash -s -- -y

source ~/.bashrc

npm i -g yarn

source ~/.bashrc

git clone git@github.com:coopengo/coog-portal

cd coog-portal

yarn
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

Start tests on a module:

```bash
coog test manual -- <module_name> [module_2] ...

# Use /tmp/test_cache for caching test databases
DB_CACHE=/tmp/test_cache coog test manual -- <module_name> [module_2] ...

# Convert py scenarios to rst
coog test convert [module_name]
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

Exec chain `chain_name` if module `module_name` is active:

```bash
coog chain -- <module_name> <chain_name> [chain_params]
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

### Other

Check a module status in the database:

```bash
coog module status <module_name>
```

Check the environment variables which are loaded by Coog:

```bash
coog env
```

Run a command in the context in which Coog will be loaded:

```bash
coog env run <my_command>

# Typical use case
coog env run python
```

Use proteus to connect to a running server:

```python
from proteus import config, set_xmlrpc

# Format: http://<login>:<password>@<host>:<port>/<db>/
conf = config.set_xmlrpc('http://admin:admin@localhost:8000/coog/')

Contract = Model.get('contract)
contracts = Contract.find([('status', '=', 'active')])

# From here it's business as usual
print(contracts[0].product.rec_name)
```
