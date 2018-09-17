#!/usr/bin/env python
import os
import sys
import json
import subprocess

try:
    _, source_db, target_db = sys.argv[:3]
    if len(sys.argv) == 4:
        conn_info = sys.argv[3].split(' ')
    else:
        conn_info = ['-U', 'tryton']
except ValueError:
    sys.stderr.write('''
Usage :
    generate_test_base.py <source_db> <target_db> [connexion_info]

    Designed and tested for postgresql only.

    <target_db> must be an already existing empty database.
    <connexion_info> will be passed as parameters to the psql command (use it
        to set user, host, etc...)

''')
    sys.exit()

conf_folder = os.environ.get('COOG_CONF')
if not conf_folder:
    sys.stderr.write('$COOG_CONF not set')
    sys.stderr.write(' ')
    sys.exit()

conf_file = os.path.join(conf_folder, 'db_export.json')

print('Reading configuration file')
with open(conf_file, 'r') as f:
    exclude = json.loads(f.read())

cmd = ['pg_dump', '-n', 'public'] + conn_info
for table in exclude:
    cmd += ['--exclude-table-data', table]

cmd += [source_db, '|', 'psql', '-d', target_db] + conn_info

print('Copying trimmed database')
with open(os.devnull, 'w') as devnull:
    p = subprocess.Popen(' '.join(cmd), shell=True, stdout=devnull)
    p.communicate()

# Ugly hack to remove unused lines
constraints = 'psql -c "\\d+ party_party;" '
constraints += target_db + ' ' + ' '.join(conn_info)
constraints += ' | grep "^ *TABLE"'
constraints += ' | grep "ON DELETE RESTRICT"'
constraints += ' | sed -e "s/.*TABLE \\\"\([^\\\"]*\)\\\".*FOREIGN KEY '
constraints += '(\([^)]*\)).*/\\1,\\2/"'

p = subprocess.Popen(constraints, shell=True, stdout=subprocess.PIPE)
out, errors = p.communicate()

exclude = []
for constraint in out.split('\n'):
    if not constraint:
        continue
    table, column = constraint.split(',')
    exclude.append('(SELECT ' + column + ' FROM ' + table + ')')

query = 'DELETE FROM party_party WHERE id NOT IN ('
query += ' UNION '.join(exclude) + ')'

print('Removing useless parties')
cmd = 'psql -c "' + query + '" -d ' + target_db + ' ' + ' '.join(conn_info)
with open(os.devnull, 'w') as devnull:
    p = subprocess.Popen(cmd, shell=True, stdout=devnull)
    p.communicate()
