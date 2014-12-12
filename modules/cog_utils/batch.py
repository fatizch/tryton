import os
import logging
import ConfigParser
from datetime import datetime

from celeryconfig import CELERYD_CONCURRENCY, CELERYD_TASK_LOG_FORMAT
from celery.utils.log import get_task_logger

from trytond.config import config
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import ModelView

from trytond.modules.cog_utils import coop_string

__all__ = [
    'BatchRoot',
    'ViewValidationBatch',
    ]


def get_logger(batch_name):
    logger = get_task_logger(batch_name)
    log_dir = config.get('batch', 'log_dir', '')
    if log_dir:
        handler = logging.FileHandler(os.path.join(
            log_dir, batch_name + '.log'), delay=True)
        format_string = CELERYD_TASK_LOG_FORMAT.replace('[%(name)s]', '')
        formatter = logging.Formatter(format_string)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


class BatchRoot(ModelView):
    'Root class for batches'

    @classmethod
    def __setup__(cls):
        super(BatchRoot, cls).__setup__()
        cls._default_config_items = {
            'filepath_template': u'%{BATCHNAME}/%{FILENAME}',
            'filepath_timestamp_format': u'%Y%m%d_%Hh%Mm%Ss',
            'split_mode': u'divide',
            'split_size': str(CELERYD_CONCURRENCY),
        }
        cls._config = ConfigParser.RawConfigParser()
        config_file = config.get('batch', 'config_file')
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
            item = cls._default_config_items[key]
        return item

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
    def get_batch_domain(cls, treatment_date):
        return []

    @classmethod
    def get_batch_ordering(cls):
        return None

    @classmethod
    def get_batch_field(cls):
        return 'id'

    @classmethod
    def select_ids(cls, treatment_date):
        cursor = Transaction().cursor
        SearchModel = Pool().get(cls.get_batch_search_model())
        tables, expression = SearchModel.search_domain(
            cls.get_batch_domain(treatment_date))
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
    def generate_filepath(cls, filename):
        filepath_template = cls.get_conf_item('filepath_template')
        filepath_template = filepath_template.\
            replace('%{FILENAME}', filename). \
            replace('%{BATCHNAME}', coop_string.remove_blank_and_invalid_char(
                cls.__name__))
        if '%{TIMESTAMP}' in filepath_template:
            date_format = cls.get_conf_item('filepath_timestamp_format')
            timestamp = datetime.now().strftime(date_format)
            filepath_template = filepath_template.replace('%{TIMESTAMP}',
                timestamp)
        return os.path.join(cls.get_conf_item('root_dir'), filepath_template)

    @classmethod
    def convert_to_instances(cls, ids):
        MainModel = Pool().get(cls.get_batch_main_model_name())
        return MainModel.browse(ids)

    @classmethod
    def write_batch_output(cls, _buffer, filename):
        batch_outpath = cls.generate_filepath(filename)
        batch_dirpath = os.path.dirname(batch_outpath)
        if not os.path.exists(batch_dirpath):
            os.makedirs(batch_dirpath)
        with open(batch_outpath, 'w') as f:
            f.write(_buffer)


class ViewValidationBatch(BatchRoot):
    'View validation batch'

    __name__ = 'ir.ui.view.validate'

    logger = get_logger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'ir.ui.view'

    @classmethod
    def get_batch_search_model(cls):
        return 'ir.ui.view'

    @classmethod
    def get_batch_domain(cls, treatment_date):
        Module = Pool().get('ir.module.module')
        modules = Module.search([])
        utils_module = Module.search([('name', '=', 'cog_utils')])[0]
        coop_modules = set([module.name for module in modules
                if utils_module in module.parents])
        return [('module', 'in', coop_modules)]

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        for view in objects:
            try:
                full_xml_id = view.xml_id
                if full_xml_id == '':
                    continue
                xml_id = full_xml_id.split('.')[-1]
                if view.inherit:
                    full_inherited_xml_id = view.inherit.xml_id
                    if full_inherited_xml_id.split('.')[-1] != xml_id:
                        cls.logger.warning('View %s inherits from %s but has '
                            'different id !' % (full_xml_id,
                                full_inherited_xml_id))
            except:
                cls.logger.error('Failed testing view %s' % view.id)
                raise
