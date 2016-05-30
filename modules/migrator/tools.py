#!/usr/bin/env python

from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    import psycopg2cffi as psycopg2
    from psycopg2cffi.extras import RealDictCursor

from trytond.config import config
from trytond.pool import Pool


class MigrateError(Exception):
    """Error that stops the migration of current row
    """


class MigrateWarning(Exception):
    """Recoverable error that does not prevent the migration of current row
    """


class MigrateCacheError(MigrateError):
    """Raised when a required object is not present in coog.
    """


# http://stackoverflow.com/a/12168252
# Reuse opened connection to the source database without requiring it.
def none_ctxt(a=None):
    return contextmanager(lambda: iter([a]))()


def connect_to_source():
    section = 'migration'
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


def load_objects(model, key, clause=None):
    """Perform a search on model with given clause, index all returned objects
       in a dict using key. Return the dict.
    """
    Model = Pool().get(model)
    clause = [clause] if clause else []
    objs = Model.search(clause)
    return {getattr(obj, key): obj for obj in objs}


def resolve_key(row, key, cache, dest_key=None, dest_attr=None):
    """Replace row[key] identifier by corresponding object fetched from
       cache[key].
       Raise an error if the key is not present in cache dict.

       Keyword arguments:
       row -- an sql result-set row dict
       key -- the field to access in row to get cache key value
       dest_key -- (optional) the field to set in row with the object retrieved
                  from cache. Default: use key
    """
    if not dest_key:
        dest_key = key
    try:
        obj = cache[row[key]]
        row[dest_key] = getattr(obj, dest_attr) if dest_attr else obj
    except KeyError:
        raise MigrateCacheError("Missing '%s' %s in cache" % (row[key],
            dest_key))
    return row


def remove_existing_ids(ids, model, func_key):
    """Return ids without those of objects already present in coog.
    """

    existing_ids = load_objects(model, func_key,
        (func_key, 'in', ids)).keys()
    return set(ids) - set(existing_ids)


def diff_rows(row_a, row_b):
    """Return the delta dict between row_b and row_a
    """
    return {k: v for k, v in row_b.iteritems() if row_a[k] != v}
