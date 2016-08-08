# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from sql import Column
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.transaction import Transaction
from trytond.modules.cog_utils import batch

import tools

__all__ = [
    'Migrator',
    ]


class Migrator(batch.BatchRootNoSelect):
    """Migrator"""

    __name__ = 'migrator'

    logger = logging.getLogger(__name__)
    # fields to override in __setup__
    table = None      # table name to migrate in the source database
    columns = {}      # mapping of row dict keys to table columns
    model = ''        # model name of corresponding objects in coog database
    func_key = 'id'   # model attribute to use as key when caching coog objects
    cache_obj = {}    # cache of coog objects required to migrate rows
    transcoding = {}  # contains transcoded values for rows values
    error_messages = {}

    @classmethod
    def __setup__(cls):
        super(Migrator, cls).__setup__()
        cls.__rpc__.update({'migrate': RPC(readonly=False),
                'select_ids': RPC(readonly=False)})
        cls.error_messages.update({
                'no_rows': 'No rows returned by query %s',
                })

    @classmethod
    def error_message(cls, code):
        """Get error message prefixed by its code
        """
        return '[%s] %s' % (code, cls.error_messages.get(code, code))

    @classmethod
    def select_columns(cls, tables=None):
        res = []
        for dest_col, src_col in cls.columns.iteritems():
            if src_col:
                res.append(Column(cls.table, src_col).as_(dest_col))
        return res

    @classmethod
    def init_update_cache(cls, rows):
        ids = [r[cls.func_key] for r in rows]
        cls.cache_obj['update'] = tools.load_objects(
            cls.model, cls.func_key,
            (cls.func_key, 'in', ids))

    @classmethod
    def init_cache(cls, rows):
        """Fill in cls.cache_obj with existing objects required to migrate rows
        """
        if cls.do_update():
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
        rows = cursor.fetchall()
        for row in rows:
            row = cls.sanitize(row)
        num_rows_query = len(rows)
        rows = [r for r in rows if getattr(r, cls.func_key, 1)]
        cls.logger.debug(('Result of sql query => %s rows, %s after '
                'sanitize') % (num_rows_query, len(rows)))
        return rows

    @classmethod
    def sanitize(cls, row):
        """Reformat row to match target expected format and perform
           sanity checks.
           Set row func key to None to flag a row that must not be migrated.
        """
        for k, v in row.iteritems():
            if isinstance(v, basestring):
                row[k] = v.strip()
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
    def select_ids(cls, treatment_date=None, extra_args=None):
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
        if 'in' in extra_args:
            ids = eval(extra_args.get('in', '[]'))
        elif 'in-file' in extra_args:
            with open(extra_args['in-file']) as f:
                ids = eval(f.read())
        elif cls.table and cls.columns:
            ids = cls.select_all_ids(extra_args)
        if 'not-in' in extra_args:
            excluded = eval(extra_args.get('not-in', '[]'))
        elif 'not-in-file' in extra_args:
            with open(extra_args['not-in-file']) as f:
                excluded = eval(f.read())
        res = [[x] for x in set(ids) - set(excluded)]
        return res

    @classmethod
    def get_batch_args_name(cls):
        return ['in', 'in-file', 'not-in', 'not-in-file']

    @classmethod
    def extra_migrator_names(cls):
        """Return which others migrators to call once current migrator has
           created objects.
        """
        return []

    @classmethod
    def migrate(cls, ids, conn=None):
        with (tools.connect_to_source() if not conn
                  else tools.none_ctxt(conn)) as conn:
            cursor = conn.cursor()
            select = cls.query_data(ids)
            if select:
                rows = cls.run_query(select, cursor)
                if rows:
                    cls.init_cache(rows)
                    return cls.migrate_rows(rows)
                else:
                    cls.logger.error(cls.error_message('no_rows') % (select,))

    @classmethod
    def migrate_rows(cls, rows, conn=None):
        pool = Pool()
        to_upsert = []
        for row in rows:
            try:
                row = cls.populate(row)
            except tools.MigrateError as e:
                cls.logger.error(e)
            else:
                to_upsert.append(row)
        result = cls.upsert_records(to_upsert)
        for migrator in cls.extra_migrator_names():
            pool.get(migrator).migrate(result, conn)
        return result

    @classmethod
    def upsert_records(cls, rows):
        if not cls.do_update():
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
        if rows:
            to_create = {}
            for row in rows:
                to_create[row[cls.func_key]] = {k: row[k]
                    for k in row if k in Model._fields
                    }
            Model.create(to_create.values())
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
        if rows:
            to_update = {}
            for row in rows:
                obj = cls.cache_obj['update'][row[cls.func_key]]
                to_update[row[cls.func_key]] = [
                    [obj], {k: row[k] for k in row if k in Model._fields}
                    ]
            Model.write(*sum(to_update.values(), []))
            return rows
        return []

    @classmethod
    def do_update(cls):
        """Return True if the update flag was set. Otherwise, return False"""
        return Transaction().context.get('batch_update', False)

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        with Transaction().set_context(
                batch_update=extra_args.get(
                    'extra_args', 'false').lower() == 'true'):
            objs = cls.migrate(ids)
            if objs is not None:
                # string to display in 'result' column of `coog batch qlist`
                return '%s|%s' % (len(objs), len(ids))

    @classmethod
    def select_all_ids(cls, extra_args=None):
        """Return all values for given column in table.
           If model and field are present, remove from returned list all ids of
           objects that are already existing.
        """
        with tools.connect_to_source().cursor() as cursor:
            select_key = cls.columns[cls.func_key]
            select = cls.table.select(*[Column(cls.table, select_key)],
                order_by=(Column(cls.table, select_key)))
            for kw in ('limit', 'offset'):
                if extra_args and kw in extra_args:
                    setattr(select, kw, int(extra_args[kw]))
            cursor.execute(*select)
            vals = [x[select_key] for x in cursor.fetchall()]
            if (cls.model and cls.func_key != 'id'
                    and 'update' in extra_args
                    and extra_args['update'].lower() != 'true'):
                vals = tools.remove_existing_ids(vals, cls.model, cls.func_key)
            return vals
