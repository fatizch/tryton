# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Column, Table

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    import psycopg2cffi as psycopg2
    from psycopg2cffi.extras import RealDictCursor

from trytond.config import config
from trytond.pool import Pool
from trytond.transaction import Transaction


def connect_to_source():
    section = 'migration'
    if config.has_section(section):
        conn = psycopg2.connect(
            database=config.get(section, 'database'),
            user=config.get(section, 'user'),
            password=config.get(section, 'password'),
            host=config.get(section, 'host'),
            connect_timeout=5,  # in seconds
            cursor_factory=RealDictCursor)
        schema = config.get(section, 'schema')
        if schema:
            conn.cursor().execute("SET SCHEMA '%s'" % schema)
        return conn


CONNECT_SRC = connect_to_source()


def diff_rows(row_a, row_b):
    """Return the delta dict between row_b and row_a
    """
    return {k: v for k, v in row_b.iteritems() if row_a[k] != v}


def cache_from_search(model, key, clause=None):
    """Perform a search on model with given clause, index all returned objects
       in a dict using key. Return the dict.

       Use it only if the more efficient cache_from_query() method is not an
       option (eg performing search on a function field).
    """
    Model = Pool().get(model)
    clause = [clause] if clause else []
    objs = Model.search(clause)
    return {getattr(obj, key): obj for obj in objs}


def cache_from_query(table_name, keys, vals=None, target='id'):
    """Build a cache dictionary, mapping combinations of existing values for
       tuple keys to corresponding records.
       Optional vals tuple is used to build a WHERE...IN clause to restrict the
       set of records to cache.
    """
    if vals:
        assert len(vals) == 2
        if not vals[1]:
            return {}
    table = Table(table_name)
    select = table.select(*[Column(table, k) for k in list(keys) + [target]])
    if vals:
        select.where = (Column(table, vals[0]).in_(list(vals[1])))
    cursor = Transaction().connection.cursor()
    cursor.execute(*select)
    return {x[0] if len(x) == 2 else x[:-1]: x[-1] for x in cursor.fetchall()}
