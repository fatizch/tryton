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


DB_USER = parse_environ('ADMIN_DB_USER', 'tryton')
DB_PASSWORD = parse_environ('ADMIN_DB_PASSWORD', 'tryton')
COOG_DB_USER = parse_environ('COOG_DB_USER', 'tryton')
COOG_DB_PASSWORD = parse_environ('COOG_DB_PASSWORD', 'tryton')
DB_HOST = parse_environ('COOG_POSTGRES_HOST', 'localhost')
DB_NAME = parse_environ('COOG_DB_NAME', 'coog')
DB_PORT = parse_environ('COOG_POSTGRES_PORT', 5432)
FORCE_UPDATE = parse_environ('FORCE_UPDATE', False)
DB_ROOT = parse_environ('POSTGRES_ADMIN_DB_NAME', '')


assert all([DB_NAME, DB_PASSWORD, DB_HOST, DB_USER, DB_PORT]
    ), 'DB connection data not set'


def get_connection(new=False, use_coog=False):
    try:
        conn_string = "user='%s' host='%s' password='%s' port='%s'"
        conn_args = (DB_USER if not use_coog else COOG_DB_USER, DB_HOST,
            DB_PASSWORD if not use_coog else COOG_DB_PASSWORD, DB_PORT)
        if not new:
            conn_string += " dbname='%s'"
            conn_args += (DB_NAME,)
        elif new and DB_ROOT:
            conn_string += " dbname='%s'"
            conn_args += (DB_ROOT,)
        connection = psycopg2.connect(conn_string % conn_args)
        connection.autocommit = True
        cur = connection.cursor()
        if new:
            # Will crash if the database already exists
            cur.execute("CREATE DATABASE %s OWNER %s;" % (DB_NAME, COOG_DB_USER))
            if DB_ROOT:
                cur.close()
                connection.close()
                return get_connection(use_coog=True)

        return connection
    except psycopg2.OperationalError:
        if new:
            raise
        return None
    except psycopg2.ProgrammingError:
        return None


def main():
    conn = get_connection()
    created = False

    if conn:
        # Database already exists: Do nothing
        print('already exists')
    else:
        conn = get_connection(new=True)
        print('Create database')
        created = True

    if FORCE_UPDATE or created:
        print('UPDATING DATABASE')
        os.system('echo "enT2BduLKrxI" > /tmp/trpass')
        os.system('TRYTONPASSFILE=/tmp/trpass ep admin -d %s '
            '--email %s -u ir res' % (
                DB_NAME, 'admin@coopengo.com'))
