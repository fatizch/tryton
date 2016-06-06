import logging

from sql import Column

from trytond.pool import Pool
from trytond.rpc import RPC

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
    def init_cache(cls, rows):
        """Fill in cls.cache_obj with existing objects required to migrate rows
        """
        pass

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
    def extra_migrator_names(cls):
        """Return which others migrators to call once current migrator has
           created objects.
        """
        return []

    @classmethod
    def migrate(cls, ids, cursor_src=None):
        with (tools.connect_to_source().cursor() if not cursor_src
              else tools.none_ctxt(cursor_src)) as cursor_src:
            select = cls.query_data(ids)
            if select:
                rows = cls.run_query(select, cursor_src)
                if rows:
                    cls.init_cache(rows)
                    return cls.migrate_rows(rows)
                else:
                    cls.logger.error(cls.error_message('no_rows') % (select,))

    @classmethod
    def migrate_rows(cls, rows, cursor_src=None):
        pool = Pool()
        Model = pool.get(cls.model)
        to_create = {}
        for row in rows:
            try:
                row = cls.populate(row)
            except tools.MigrateError as e:
                cls.logger.error(e)
                continue
            to_create[row[cls.func_key]] = {k: row[k]
                for k in row if k in Model._fields}
        if to_create:
            Model.create(to_create.values())
            for migrator in cls.extra_migrator_names():
                pool.get(migrator).migrate(to_create.keys(), cursor_src)
        return to_create

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
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
            if cls.model and cls.func_key != 'id':
                vals = tools.remove_existing_ids(vals, cls.model, cls.func_key)
            return vals
