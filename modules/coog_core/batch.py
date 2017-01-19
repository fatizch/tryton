# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import shutil
import logging
import ConfigParser
from datetime import datetime, date
import uuid

from trytond import backend
from trytond.config import config
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import ModelView, ModelSQL, Model, fields
from trytond.perf_analyzer import PerfLog, profile, logger as perf_logger

import coog_string


__all__ = [
    'BatchRoot',
    'BatchRootNoSelect',
    'ViewValidationBatch',
    'CleanDatabaseBatch',
    'BatchParamsConfig',
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


class BatchRoot(ModelView):
    'Root class for batches'

    @classmethod
    def __setup__(cls):
        super(BatchRoot, cls).__setup__()
        cls._default_config_items = {
            'root_dir': config.get('batch', 'log_dir', default=''),
            'filepath_template': u'%{BATCHNAME}/%{FILENAME}',
            'filepath_timestamp_format': u'%Y%m%d_%Hh%Mm%Ss',
            'job_size': '1000',
            'transaction_size': '0'
        }
        cls._config = ConfigParser.RawConfigParser()
        config_file = os.environ.get('TRYTOND_BATCH_CONFIG')
        if config_file:
            try:
                with open(config_file, 'r') as fconf:
                    cls._config.readfp(fconf)
            except IOError:
                pass
        for section in cls._config.sections():
            if cls._config.has_option(section, 'filepath_template'):
                assert('%{FILENAME}' in cls._config.get(section,
                    'filepath_template'))

    @classmethod
    def get_conf_item(cls, key):
        if cls._config.has_option(cls.__name__, key):
            item = cls._config.get(cls.__name__, key)
        elif cls._config.has_option('default', key):
            item = cls._config.get('default', key)
        else:
            item = cls._default_config_items.get(key, None)
        return item

    @classmethod
    def check_params(cls, params):
        logger = logging.getLogger(cls.__name__)
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
    def get_batch_domain(cls, **kwargs):
        return []

    @classmethod
    def get_batch_ordering(cls):
        return None

    @classmethod
    def get_batch_field(cls):
        return 'id'

    @classmethod
    def select_ids(cls, **kwargs):
        cursor = Transaction().connection.cursor()
        SearchModel = Pool().get(cls.get_batch_search_model())
        tables, expression = SearchModel.search_domain(
            cls.get_batch_domain(**kwargs))
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
    def generate_filepath(cls, filename='', makedirs=True):
        filepath_template = cls.get_conf_item('filepath_template')
        filepath_template = filepath_template.\
            replace('%{FILENAME}', filename). \
            replace('%{BATCHNAME}', coog_string.slugify(cls.__name__))
        if '%{TIMESTAMP}' in filepath_template:
            date_format = cls.get_conf_item('filepath_timestamp_format')
            timestamp = datetime.now().strftime(date_format)
            filepath_template = filepath_template.replace('%{TIMESTAMP}',
                timestamp)
        filepath = os.path.join(cls.get_conf_item('root_dir'),
            filepath_template)
        dirpath = os.path.dirname(filepath)
        if makedirs and not os.path.exists(dirpath):
            os.makedirs(dirpath, 0o755)  # 755 permissions in octal notation
        return filepath

    @classmethod
    def convert_to_instances(cls, ids):
        MainModel = Pool().get(cls.get_batch_main_model_name())
        return MainModel.browse(ids)

    @classmethod
    def write_batch_output(cls, _buffer, filename):
        batch_outpath = cls.generate_filepath(filename)
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


class BatchRootNoSelect(BatchRoot):
    "Root class for batches that don't query the database."

    @classmethod
    def __setup__(cls):
        super(BatchRootNoSelect, cls).__setup__()
        cls._default_config_items.update({'job_size': '0'})

    @classmethod
    def convert_to_instances(cls, ids):
        return []

    @classmethod
    def get_batch_main_model_name(cls):
        raise ''

    @classmethod
    def get_batch_search_model(cls):
        raise ''

    @classmethod
    def select_ids(cls, **kwargs):
        return []


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
            module=None, drop_const=None, drop_index=None):
        tables = []
        buf = []
        TableHandler = backend.get('TableHandler')
        pool = Pool()
        for model in objects:
            try:
                c = pool.get(model.model)
            except:
                buf.append('DROP TABLE "%s";' % model.model.replace('.', '_'))
                buf.append('DROP SEQUENCE "%s_id_seq";' %
                    model.model.replace('.', '_'))
                buf.append('DROP TABLE "%s__history";' %
                    model.model.replace('.', '_'))
                buf.append('DROP SEQUENCE "%s__history___id_seq";' %
                    model.model.replace('.', '_'))
                continue
            if not issubclass(c, ModelSQL):
                cls.logger.debug('not SQL model: %s' % model)
                continue
            if c.table_query():
                cls.logger.debug('model is table_query: %s' % model)
                continue
            fields = [k for k, v in c._fields.iteritems()
                if cls.check_field(v)]
            table = TableHandler(c)
            cls.check_model(buf, model.model, fields, table)
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
        cls.write_batch_output('\n'.join(buf), 'clean.sql')


class BatchParamsConfig(Model):
    'Batch Parameters Configuration'

    __name__ = 'batch.params_config'

    @classmethod
    def get_computed_params(cls, params):
        c_params = params.copy()
        if params.get('treatment_date'):
            c_params['treatment_date'] = datetime.strptime(
                params['treatment_date'], '%Y-%m-%d').date()
        return c_params
