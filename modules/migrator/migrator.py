# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import logging
import tools

from random import shuffle
from sql import Column

from trytond.modules.coog_core import batch
from trytond.pool import Pool
from trytond.rpc import RPC


__all__ = [
    'Migrator',
    ]


class MigrateError(Exception):
    """Error that stops the migration of current row
    """
    def __init__(self, error_code, error_message):
        super(MigrateError, self).__init__(error_message)
        self.code = error_code


class Migrator(batch.BatchRootNoSelect):
    """Migrator"""

    __name__ = 'migrator'

    logger = logging.getLogger(__name__)
    # fields to override in __setup__
    table = None         # table name to migrate in the source database
    columns = {}         # mapping of row dict keys to table columns
    model = ''           # model name of corresponding records in coog database
    func_key = 'id'      # attribute to use as key when caching coog records
    cache_obj = {}       # cache of coog objects required to migrate rows
    transcoding = {}     # contains transcoded values for rows values
    error_messages = {}  # errors codes/messages mapping

    @classmethod
    def __setup__(cls):
        super(Migrator, cls).__setup__()
        cls.__rpc__.update({'migrate': RPC(readonly=False),
                'select_ids': RPC(readonly=False)})
        cls.error_messages.update({
                'no_rows': 'No rows returned by query %s',
                'cache_miss': "[%s] Missing '%s' in cache to set '%s' field",
                'no_update': ("no --update mode available for this batch as "
                    "specified func_key is 'id'"),
                })

    @classmethod
    def error_message(cls, code):
        """Get error message prefixed by its code
        """
        return '%%s: [%s/%s] %s' % (cls.__name__, code,
            cls.error_messages.get(code, code))

    @classmethod
    def raise_error(cls, row, error_code, error_msg_args=None):
        if not error_msg_args:
            error_msg_args = []
        error_msg_args = [row[cls.func_key]
            if row and row.get(cls.func_key, None) else '?'] + list(
                error_msg_args)
        raise MigrateError(error_code,
            cls.error_message(error_code) % tuple(error_msg_args))

    @classmethod
    def cast_extra_args(cls, **kwargs):
        if kwargs.get('update', None) and isinstance(kwargs['update'],
                basestring):
            kwargs['update'] = kwargs['update'].lower() in ('1',
                'true')
        if kwargs.get('update', None) and cls.func_key == 'id':
            cls.raise_error(None, 'no_update')
        return kwargs

    @classmethod
    def select_columns(cls, tables=None):
        res = []
        for dest_col, src_col in cls.columns.iteritems():
            if src_col:
                res.append(Column(cls.table, src_col).as_(dest_col))
        return res

    @classmethod
    def init_update_cache(cls, rows):
        """Fill in cls.cache_obj with  objects to update.
        """
        ids = [r[cls.func_key] for r in rows]
        cls.cache_obj['update'] = tools.cache_from_query(cls.model.replace(
                '.', '_'), (cls.func_key,), (cls.func_key, ids))

    @classmethod
    def init_cache(cls, rows, **kwargs):
        """Fill in cls.cache_obj with existing objects required to migrate rows
        """
        if kwargs.get('update', False):
            cls.init_update_cache(rows)

    @classmethod
    def query_data(cls, ids):
        """Return query to fetch all data needed to create target objects
           from ids
        """
        select = cls.table.select(*cls.select_columns())
        if ids:
            select_key = cls.columns[cls.func_key]
            select.where = Column(cls.table, select_key).in_(ids)
            select.order_by = (Column(cls.table, select_key))
        return select

    @classmethod
    def run_query(cls, select, cursor):
        """Run query and returned rows once sanitized.
        """
        cls.logger.debug("Execute sql query '%s'" % (select,))
        cursor.execute(*select)
        rows_all = cursor.fetchall()
        rows = [r for r in rows_all if cls.sanitize(r)]
        cls.logger.debug(('Result of sql query => %s rows, %s after '
                'sanitize') % (len(rows_all), len(rows)))
        return rows

    @classmethod
    def sanitize(cls, row):
        """Reformat row to match target expected format and perform sanity
           checks.
           Return None to discard the row from the list of rows to migrate.
        """
        for k in cls.columns:
            if k in row:
                if isinstance(row[k], basestring):
                    row[k] = row[k].strip()
            else:
                row[k] = None
        # If row key is in transcoding, replace row value by transcoded one
        for key in cls.transcoding.keys():
            if key in row:
                row[key] = cls.transcoding[key].get(row[key], row[key])
        return row

    @classmethod
    def populate(cls, row):
        """Populate row with fields used in target model.
        """
        return row

    @classmethod
    def select_ids(cls, **kwargs):
        """Return ids of objects to migrate.
           By default return all cls.column values of cls.table except ids
           corresponding to existing instances of cls.model.
           Default selection can be overidden by passing following parameters
           to extra_args :
                --in            [ID_LIST]
                --in-file       FILENAME
                --not-in        [ID_LIST]
                --not-in-file  FILENAME
        """
        ids = []
        excluded = []
        kwargs.update(cls.cast_extra_args(kwargs))
        if 'not-in' in kwargs:
            excluded = eval(kwargs.get('not-in', '[]'))
        elif 'not-in-file' in kwargs:
            with open(kwargs['not-in-file']) as f:
                excluded = eval(f.read())
        if 'in' in kwargs:
            ids = eval(kwargs.get('in', '[]'))
        elif 'in-file' in kwargs:
            with open(kwargs['in-file']) as f:
                ids = eval(f.read())
        # By default query all table ids
        elif cls.table and cls.columns:
            cursor = tools.CONNECT_SRC.cursor()
            select, select_key = cls.select(kwargs)
            for kw in ('limit', 'offset'):
                if kwargs and kw in kwargs:
                    setattr(select, kw, int(kwargs[kw]))
            cursor.execute(*select)
            ids = cls.select_extract_ids(select_key, cursor.fetchall())
        cls.logger.info('%s ids before removal' % len(ids))
        if cls.model and not kwargs.get('update', False) and \
                cls.func_key != 'id':
            ids = cls.select_remove_ids(ids, excluded)
        cls.logger.info('%s ids after removal' % len(ids))
        ids = cls.select_group_ids(ids)
        cls.logger.info('%s groups from ids' % len(ids))
        if kwargs.get('shuffle', False):
            shuffle(ids)
        return ids

    @classmethod
    def select(cls, **kwargs):
        """Return ids selection query and which model key to use to retrieve
           existing ids
        """
        select_key = cls.columns[cls.func_key]
        select = cls.table.select(*[Column(cls.table, select_key)],
            order_by=(Column(cls.table, select_key)))
        return select, cls.func_key

    @classmethod
    def select_remove_ids(cls, ids, excluded, **kwargs):
        """Return ids after having removed those of records already present
           in coog.
        """
        table_name = cls.model.replace('.', '_')
        existing_ids = tools.cache_from_query(table_name,
            (cls.func_key,)).keys()
        return list(set(ids) - set(excluded) - set(existing_ids))

    @classmethod
    def select_group_ids(cls, ids):
        """Group together ids that must be handled by same job
        """
        return [[x] for x in ids]

    @classmethod
    def select_extract_ids(cls, select_key, rows):
        return [x[cls.columns[select_key]] for x in rows]

    @classmethod
    def extra_migrator_names(cls):
        """Return which others migrators to call once current migrator has
           created objects.
        """
        return []

    @classmethod
    def migrate(cls, ids, **kwargs):
        cls.logger.info('%s is starting to migrate %s ids. Extra args: %s' % (
                cls.__name__, len(ids), kwargs))
        select = cls.query_data(ids)
        res = {}
        if ids and select:
            rows = cls.run_query(select, tools.CONNECT_SRC.cursor())
            if not rows:
                cls.logger.warning(cls.error_message(
                    'no_rows') % (None, select,))
            cls.init_cache(rows)
            res.update(cls.migrate_rows(rows, ids) or {})
        else:
            cls.logger.error(cls.error_message('no_rows') % (None, select,))
        return res

    @classmethod
    def migrate_rows(cls, rows, ids):
        pool = Pool()
        to_upsert = {}
        for row in rows:
            try:
                row = cls.populate(row)
            except MigrateError as e:
                cls.logger.error(e)
                continue
            to_upsert[row[cls.func_key]] = row
        if to_upsert:
            cls.upsert_records(to_upsert.values())
            for migrator in cls.extra_migrator_names():
                pool.get(migrator).migrate(to_upsert.keys())
        return to_upsert

    @classmethod
    def upsert_records(cls, rows, **kwargs):
        Model = Pool().get(cls.model)
        if not kwargs['update']:
            return cls.create_records(rows)
        result, to_create, to_update = [], [], []
        for row in rows:
            if row[cls.func_key] in cls.cache_obj['update']:
                to_update.append(row)
            else:
                to_create.append(row)
        result += cls.create_records(to_create)
        result += cls.update_records(to_update)
        return result

    @classmethod
    def create_records(cls, rows):
        """Create records from a list of rows and
           return the list of ids which were successfully created.
        """
        pool = Pool()
        Model = pool.get(cls.model)
        rows = [{k: row[k] for k in row if k in set(Model._fields) - {'id', }}
            for row in rows]
        if rows:
            Model.create(rows)
            return rows
        return []

    @classmethod
    def update_records(cls, rows):
        """Update records from a list of rows.
           For the moment relational fields are not supported, eg One2Many.
           Returns a list of successfully updated ids.
        """
        pool = Pool()
        Model = pool.get(cls.model)
        rows = [{k: row[k] for k in row if k in set(Model._fields) - {'id', }}
            for row in rows]
        if rows:
            to_update = {}
            for row in rows:
                obj = Model(cls.cache_obj['update'][row[cls.func_key]])
                to_update[row[cls.func_key]] = [[obj], row]
            Model.write(*sum(to_update.values(), []))
            return rows
        return []

    @classmethod
    def execute(cls, objects, ids, **kwargs):
        kwargs.update(cls.cast_extra_args(kwargs))
        objs = cls.migrate(ids)
        if objs is not None:
            # string to display in 'result' column of `coog batch qlist`
            return '%s|%s' % (len(objs), len(ids))

    @classmethod
    def resolve_key(cls, row, key, cache_name, dest_key=None, dest_attr=None):
        """Replace row[key] with the corresponding value in the cache.
           Raise an error if row[key] is not present in cache.
        """
        if not dest_key:
            dest_key = key
        if row[key] is not None:
            try:
                obj = cls.cache_obj[cache_name][row[key]]
                row[dest_key] = getattr(obj, dest_attr) if dest_attr else obj
            except KeyError:
                cls.raise_error(row, 'cache_miss', (cache_name, row[key],
                    dest_key))
        return row

    @classmethod
    def check_params(cls, params):
        super(Migrator, cls).check_params(params)
        params.setdefault('update', False)
        return params
