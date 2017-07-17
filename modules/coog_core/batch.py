# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import shutil
import logging
import ConfigParser
from datetime import datetime, date
import uuid
import itertools

from trytond import backend
from trytond.config import config
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import ModelView, ModelSQL, Model, fields
from trytond.perf_analyzer import PerfLog, profile, logger as perf_logger

import model
import coog_string

try:
    import async.broker as async_broker
    if config.get('async', 'celery', default=None) is not None:
        async_broker.set_module('celery')
    elif config.get('async', 'rq', default=None) is not None:
        async_broker.set_module('rq')
    else:
        raise Exception('no async broker')
except Exception as error:
    logging.getLogger(__name__).error(error)
    async_broker = None


__all__ = [
    'BatchRoot',
    'BatchRootNoSelect',
    'ViewValidationBatch',
    'CleanDatabaseBatch',
    'NoSelectBatchExample',
    'BatchParamsConfig',
    'MemorySavingBatch',
    ]


def analyze(meth):
    def wrap(cls, *args, **kwargs):
        m = meth
        try:
            p = PerfLog()
            p.on_enter(Transaction().user,
                uuid.uuid4().hex, cls.__name__, [], {})
            wrapped_meth = profile(m)
        except:
            perf_logger.exception('batch: error on enter')
        else:
            m = wrapped_meth
        ret = m(cls, *args, **kwargs)
        try:
            PerfLog().on_leave(unicode(
                    {'args': args, 'kwargs': kwargs, 'return': ret}))
        except:
            perf_logger.exception('batch: error on leave')
        return ret
    return wrap


def load_batch_config():
    config = ConfigParser.RawConfigParser()
    config_file = os.environ.get('TRYTOND_BATCH_CONFIG')
    if config_file:
        try:
            with open(config_file, 'r') as fconf:
                config.readfp(fconf)
        except IOError:
            pass
    return config


class BatchRoot(ModelView):
    'Root class for batches'

    _config = load_batch_config()

    @classmethod
    def __setup__(cls):
        super(BatchRoot, cls).__setup__()
        cls._default_config_items = {
            'job_size': '1000',
            'transaction_size': '0',
        }

    @classmethod
    def get_batch_configuration(cls):
        config = {}
        if cls._config.has_section(cls.__name__):
            for key, value in cls._config.items(cls.__name__):
                config[key] = value
        return config

    @classmethod
    def serializable_params(cls, params):
        serializable = {}

        for key, value in params.items():
            if isinstance(value, date):
                serializable[key] = value.strftime('%Y-%m-%d')
            else:
                serializable[key] = value
        return serializable

    @classmethod
    def parse_params(cls, params):
        logger = logging.getLogger(cls.__name__)
        filepath_template = params.get('filepath_template', None)
        if filepath_template:
            assert('%{FILENAME}' in filepath_template)
        if not params.get('connection_date'):
            logger.warning('Missing parameter: connection_date')
        params.setdefault('connection_date', date.today())
        BatchParamsConfig = Pool().get('batch.params_config')
        params = BatchParamsConfig.get_computed_params(params)
        return params

    @classmethod
    def execute(cls, objects, ids):
        raise NotImplementedError

    @classmethod
    def get_batch_main_model_name(cls):
        raise NotImplementedError

    @classmethod
    def get_batch_search_model(cls):
        raise NotImplementedError

    @classmethod
    def get_batch_domain(cls, *args, **kwargs):
        return []

    @classmethod
    def get_batch_ordering(cls):
        return None

    @classmethod
    def get_batch_field(cls):
        return 'id'

    @classmethod
    def select_ids(cls, *args, **kwargs):
        cursor = Transaction().connection.cursor()
        SearchModel = Pool().get(cls.get_batch_search_model())
        tables, expression = SearchModel.search_domain(
            cls.get_batch_domain(*args, **kwargs))
        main_table, _ = tables[None]

        def convert_from(table, tables):
            right, condition = tables[None]
            if table:
                table = table.join(right, 'LEFT', condition)
            else:
                table = right
            for k, sub_tables in tables.iteritems():
                if k is None:
                    continue
                table = convert_from(table, sub_tables)
            return table
        table = convert_from(None, tables)
        search_column = getattr(main_table, cls.get_batch_field())
        cursor.execute(*table.select(search_column, where=expression,
                order_by=search_column))
        res = cursor.fetchall()
        return res

    @classmethod
    def generate_filepath(cls, filename='', makedirs=True, **kwargs):
        filepath_template = kwargs.get('filepath_template')
        filepath_template = filepath_template.\
            replace('%{FILENAME}', filename). \
            replace('%{BATCHNAME}', coog_string.slugify(cls.__name__))
        if '%{TIMESTAMP}' in filepath_template:
            date_format = kwargs.get('filepath_timestamp_format')
            timestamp = datetime.now().strftime(date_format)
            filepath_template = filepath_template.replace('%{TIMESTAMP}',
                timestamp)
        filepath = os.path.join(cls.kwargs('root_dir'),
            filepath_template)
        dirpath = os.path.dirname(filepath)
        if makedirs and not os.path.exists(dirpath):
            os.makedirs(dirpath, 0o755)  # 755 permissions in octal notation
        return filepath

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        MainModel = Pool().get(cls.get_batch_main_model_name())
        return MainModel.browse([x[0] for x in ids])

    @classmethod
    def on_job_fail(cls, task_id, objects, exc, *args, **kwargs):
        '''
        This method is called on failure by the celery Task itself
        If the task has been enqueued and does not come from a batch,
        A user variable should be set in the kwargs.
        '''
        user = kwargs.get('user', None)
        if user:
            Pool().get('event').notify_events(objects,
                'asynchronous_task_failure', description=exc.message,
                **kwargs)

    @classmethod
    def on_job_success(cls, task_id, objects, retval, *args, **kwargs):
        '''
        This method is called on success by the celery Task itself
        If the task has been enqueued and does not come from a batch,
        A user variable should be set in the kwargs.
        '''
        user = kwargs.get('user', None)
        if user:
            Pool().get('event').notify_events(objects,
                'asynchronous_task_success', description=str(retval),
                **kwargs)

    @classmethod
    def write_batch_output(cls, _buffer, filename, **kwargs):
        batch_outpath = cls.generate_filepath(filename, **kwargs)
        with open(batch_outpath, 'w') as f:
            f.write(_buffer)

    @classmethod
    def archive_treated_files(cls, files, archive_path, treatment_date,
            prefix='treated'):
        assert isinstance(prefix, basestring)
        for file_name, file_path in files:
            treated_file_name = '%s_%s_%s' % (prefix, str(treatment_date),
                file_name)
            shutil.move(file_path, os.path.join(archive_path,
                    treated_file_name))

    @classmethod
    def get_file_names_and_paths(cls, path):
        if os.path.isfile(path):
            files = [(os.path.basename(path), path)]
        else:
            files = [(f, os.path.join(path, f)) for f in os.listdir(path)
                if os.path.isfile(os.path.join(path, f))]
        return files

    @classmethod
    def enqueue_filter_objects(cls, records):
        return [x for x in records
            if x.__name__ == cls.get_batch_main_model_name()]

    @classmethod
    def _enqueue(cls, records, params, **kwargs):
        assert async_broker
        broker = async_broker.get_module()
        assert broker
        broker.enqueue(cls.__name__, 'batch_exec', (cls.__name__, records,
                params), **kwargs)

    @classmethod
    @model.post_transaction(model.BrokerCheckDataManager)
    def enqueue(cls, records, params, **kwargs):
        '''
        enqueue a new job
        ex: ViewValidationBatch.enqueue([(100,), (101,)], {'crash': 100})
        '''
        cls._enqueue(records, params, **kwargs)


class BatchRootNoSelect(BatchRoot):
    "Root class for batches that don't query the database."

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        return ids[:]

    @classmethod
    def get_batch_main_model_name(cls):
        raise ''

    @classmethod
    def get_batch_search_model(cls):
        raise ''

    @classmethod
    def select_ids(cls, **kwargs):
        return [(0,)]


class NoSelectBatchExample(BatchRootNoSelect):
    'Batch No Select Example'

    __name__ = 'coog.noselect_batch_example'

    @classmethod
    def execute(cls, objects, ids):
        return 'objects: %s - ids: %s' % (objects, ids)


class ViewValidationBatch(BatchRoot):
    'View validation batch'

    __name__ = 'ir.ui.view.validate'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'ir.ui.view'

    @classmethod
    def get_batch_search_model(cls):
        return 'ir.ui.view'

    @classmethod
    def get_batch_domain(cls, crash=None):
        Module = Pool().get('ir.module')
        modules = Module.search([])
        utils_module = Module.search([('name', '=', 'coog_core')])[0]
        coog_modules = set([module.name for module in modules
                if utils_module in module.parents] + ['coog_core'])
        return [('module', 'in', coog_modules)]

    @classmethod
    @analyze
    def execute(cls, objects, ids, crash=None):
        logger = logging.getLogger(cls.__name__)
        # Extra arg to make batch crash for test
        crash = crash and int(crash)
        for view in objects:
            if crash and view.id == crash:
                raise Exception('Crash for fun')
            full_xml_id = view.xml_id
            if full_xml_id == '':
                continue
            xml_id = full_xml_id.split('.')[-1]
            if view.inherit:
                full_inherited_xml_id = view.inherit.xml_id
                if full_inherited_xml_id.split('.')[-1] != xml_id:
                    logger.warning('View %s inherits from %s but has '
                        'different id !' % (full_xml_id,
                            full_inherited_xml_id))
        logger.info('%d views checked' % len(objects))


class CleanDatabaseBatch(BatchRoot):
    'Clean Database Batch'

    __name__ = 'ir.model.cleandb'
    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(CleanDatabaseBatch, cls).__setup__()
        cls._default_config_items.update({
                'filepath_template': u'%{BATCHNAME}/%{FILENAME}',
                'filepath_timestamp_format': u'%Y%m%d_%Hh%Mm%Ss',
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'ir.model'

    @classmethod
    def get_batch_search_model(cls):
        return 'ir.model'

    @classmethod
    def get_batch_domain(cls, connection_date, treatment_date, module=None,
            drop_const=None, drop_index=None):
        return module and [('module', '=', module)]

    @classmethod
    def check_field(cls, field):
        return not isinstance(field, (fields.Function, fields.Many2Many,
                fields.One2Many, fields.Property))

    @classmethod
    def check_model(cls, buf, model, fields, table):
        fields = set(fields)
        columns = set(table._columns.keys())
        diff = columns - fields
        if diff:
            for col in diff:
                buf.append('ALTER TABLE "%s" DROP COLUMN "%s";' %
                    (table.table_name, col))
        else:
            cls.logger.debug('model: %s, table: %s => ok', model,
                table.table_name)

    @classmethod
    def drop_constraints(cls, buf, table):
        for const in table._constraints:
            buf.append('ALTER TABLE "%s" DROP CONSTRAINT "%s";' %
                (table.table_name, const))

    @classmethod
    def drop_indexes(cls, buf, table):
        for index in table._indexes:
            buf.append('DROP INDEX "%s";' % index)

    @classmethod
    def create_pk(cls, buf, table):
        buf.append('ALTER TABLE "%s" ADD PRIMARY KEY(id);' % table.table_name)

    @classmethod
    def execute(cls, objects, ids, connection_date, treatment_date,
            module=None, drop_const=None, drop_index=None, **kwargs):
        tables = []
        buf = []
        TableHandler = backend.get('TableHandler')
        pool = Pool()
        for cur_model in objects:
            try:
                c = pool.get(cur_model.model)
            except:
                buf.append('DROP TABLE "%s";' % cur_model.model.replace(
                        '.', '_'))
                buf.append('DROP SEQUENCE "%s_id_seq";' %
                    cur_model.model.replace('.', '_'))
                buf.append('DROP TABLE "%s__history";' %
                    cur_model.model.replace('.', '_'))
                buf.append('DROP SEQUENCE "%s__history___id_seq";' %
                    cur_model.model.replace('.', '_'))
                continue
            if not issubclass(c, ModelSQL):
                cls.logger.debug('not SQL model: %s' % cur_model)
                continue
            if c.table_query():
                cls.logger.debug('model is table_query: %s' % cur_model)
                continue
            fields = [k for k, v in c._fields.iteritems()
                if cls.check_field(v)]
            table = TableHandler(c)
            cls.check_model(buf, cur_model.model, fields, table)
            tables.append(table)
        if drop_const is not None:
            for table in tables:
                cls.drop_constraints(buf, table)
        if drop_index is not None:
            for table in tables:
                cls.drop_indexes(buf, table)
        if drop_const is not None or drop_index is not None:
            for table in tables:
                cls.create_pk(buf, table)
        cls.write_batch_output('\n'.join(buf), 'clean.sql', **kwargs)


class BatchParamsConfig(Model):
    'Batch Parameters Configuration'

    __name__ = 'batch.params_config'

    @classmethod
    def get_computed_params(cls, params):
        c_params = params.copy()
        if params.get('treatment_date'):
            c_params['treatment_date'] = datetime.strptime(
                params['treatment_date'], '%Y-%m-%d').date()
        connection_date = params.get('connection_date')
        if connection_date and isinstance(connection_date, basestring):
            c_params['connection_date'] = datetime.strptime(
                params['connection_date'], '%Y-%m-%d').date()
        if params.get('job_size'):
            c_params['job_size'] = int(params['job_size'])
        if params.get('transaction_size'):
            c_params['transaction_size'] = int(params['transaction_size'])
        return c_params


class MemorySavingBatch(BatchRoot):
    'Memory Save Batch'

    __name__ = 'memory.save.batch'

    @classmethod
    def get_tables(cls, *args, **kwargs):
        main_model_name = cls.get_batch_main_model_name()
        return {
            main_model_name: Pool().get(main_model_name).__table__(),
            }

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        """
        Should not be overwritten. parse_select_ids should be the
        only method to create our own generator expression objects.
        """
        return cls.parse_select_ids(ids, *args, **kwargs)

    @classmethod
    def get_query_table(cls, tables, *args, **kwargs):
        return tables[cls.get_batch_main_model_name()]

    @classmethod
    def get_group_by(cls, tables, *args, **kwargs):
        return None

    @classmethod
    def get_where_clause(cls, tables, *args, **kwargs):
        return None

    @classmethod
    def get_order_by(cls, tables, *args, **kwargs):
        return None

    @classmethod
    def check_mandatory_parameters(cls, *args, **kwargs):
        raise NotImplementedError

    @classmethod
    def select_ids(cls, *args, **kwargs):
        """
        Returns generator expression of list of one tuple element.
        The tuple hold the values of selected_fields. This ensure that we have
        1 jobs per tuple of selected values.
        """
        tables = cls.get_tables()
        cls.check_mandatory_parameters(*args, **kwargs)
        cursor = Transaction().connection.cursor()
        query_table = cls.get_query_table(tables, *args, **kwargs)
        group_by = cls.get_group_by(tables, *args, **kwargs)
        where_clause = cls.get_where_clause(tables, *args, **kwargs)
        order_by = cls.get_order_by(tables, *args, **kwargs)
        fields_to_select = cls.fields_to_select(tables, *args, **kwargs)

        cursor.execute(*query_table.select(*fields_to_select,
                where=where_clause,
                group_by=group_by,
                order_by=order_by))
        if not group_by:
            return (tuple(rows) for rows in cursor.fetchall())
        else:
            return (tuple(rows) for rows in itertools.islice(
                    cursor.fetchall(), len(group_by)))

    @classmethod
    def parse_select_ids(cls, fetched_data, *args, **kwargs):
        raise NotImplementedError

    @classmethod
    def fields_to_select(cls, tables, *args, **kwargs):
        """
        Return all the fields to select in the select_ids
        """
        raise NotImplementedError

    @classmethod
    def execute(cls, objects, ids, *args, **kwargs):
        """
        Execute method only checks mandatory parameters.
        """
        cls.check_mandatory_parameters(*args, **kwargs)
