import os

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import ModelView
from trytond.config import CONFIG

__all__ = [
    'BatchRoot',
]


class BatchRoot(ModelView):
    'Root class for batches'

    @classmethod
    def __setup__(cls):
        super(BatchRoot, cls).__setup__()
        cls._error_messages.update({
            'no_batch_path': 'No Batch Path Specified'})

    @classmethod
    def get_batch_name(cls):
        if cls.__doc__:
            return cls.__doc__
        elif cls.__name__:
            return cls.__name__

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
    def get_batch_domain(cls):
        return []

    @classmethod
    def get_batch_ordering(cls):
        return None

    @classmethod
    def get_batch_field(cls):
        return 'id'

    @classmethod
    def select_ids(cls):
        SearchModel = Pool().get(cls.get_batch_search_model())
        cursor = Transaction().cursor
        qu1, qu2, tables, tables_args = SearchModel.search_domain(
            cls.get_batch_domain())
        cursor.execute(
            'SELECT DISTINCT "%s"."%s" FROM ' % (
                SearchModel._table, cls.get_batch_field())
            + ' '.join(tables) + (qu1 and ' WHERE ' + qu1 or '')
            + ' ORDER BY "%s"."%s" ASC' % (
                SearchModel._table, cls.get_batch_field()),
            tables_args + qu2)
        res = cursor.fetchall()
        return res

    @classmethod
    def get_batch_step(cls):
        return 1

    @classmethod
    def get_batch_stepping_mode(cls):
        # 'number' means the id list will be divided in chunks of X objects
        # 'divide' means the id list will be divided in X
        return 'number'

    @classmethod
    def convert_to_instances(cls, ids):
        MainModel = Pool().get(cls.get_batch_main_model_name())
        return MainModel.browse(ids)

    @classmethod
    def write_batch_output(cls, format, buffer, name):
        BATCH_PATH = CONFIG.get('batch_dir', None)
        if not BATCH_PATH:
            cls.raise_user_error('no_batch_path')
        if not os.path.exists(BATCH_PATH):
            os.makedirs(BATCH_PATH)
        good_batch_path = os.path.join(BATCH_PATH, cls.get_batch_name())
        if not os.path.exists(good_batch_path):
            os.makedirs(good_batch_path)
        f = open(os.path.join(good_batch_path, '%s.%s' % (
            name.replace(os.sep, '-'), format)), 'w')
        f.write(buffer)
        f.close()
