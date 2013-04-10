from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import ModelView

__all__ = [
    'BatchRoot',
]


class BatchRoot(ModelView):
    'Root class for batches'

    @classmethod
    def get_batch_name(cls):
        if cls.__doc__:
            return cls.__doc__[0]
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
        return 4

    @classmethod
    def get_batch_stepping_mode(cls):
        # 'number' means the id list will be divided in chunks of X objects
        # 'divide' means the id list will be divided in X
        return 'divide'

    @classmethod
    def convert_to_instances(cls, ids):
        MainModel = Pool().get(cls.get_batch_main_model_name())
        return MainModel.browse(ids)
