# encoding: utf-8
import os
import datetime
import psycopg2


def parse_environ(name, default):
    if name in os.environ:
        value = os.environ[name]
        if value in ('0', 'FALSE', 'False', 'false'):
            value = False
    else:
        value = default
    return value


DB_USER = parse_environ('COOG_DB_USER', 'tryton')
DB_PASSWORD = parse_environ('COOG_DB_PASSWORD', 'tryton')
DB_HOST = parse_environ('COOG_POSTGRES_HOST', 'localhost')
DB_NAME = parse_environ('COOG_DB_NAME', 'coog')
DB_PORT = parse_environ('COOG_DB_PORT', 5432)

assert all([DB_NAME, DB_PASSWORD, DB_HOST, DB_USER, DB_PORT]
    ), 'DB connection data not set'


def get_connection(new=False):
    try:
        conn_string = "user='%s' host='%s' password='%s' port='%s'"
        conn_args = (DB_USER, DB_HOST, DB_PASSWORD, DB_PORT)
        if not new:
            conn_string += " dbname='%s'"
            conn_args += (DB_NAME,)
        return psycopg2.connect(conn_string % conn_args)
    except psycopg2.OperationalError:
        if new:
            raise
        return None


def main():
    conn = get_connection()

    if conn:
        # Database already exists: Do nothing
        print('already exists')
        return

    conn = get_connection(new=True)
    print('Bootstrapping database')
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("CREATE DATABASE %s;" % DB_NAME)
    # }}}

    os.system('echo "enT2BduLKrxI" > /tmp/trpass')

    os.system('TRYTONPASSFILE=/tmp/trpass trytond-admin -d %s '
        '--email %s -u ir' % (
            DB_NAME, 'admin@coopengo.com'))

main()
