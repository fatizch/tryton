
from trytond.pool import PoolMeta

__all__ = ['Note']
__metaclass__ = PoolMeta

class Note:
    'Note'
    __name__ = 'ir.note'

    @classmethod
    def __setup__(cls):
        super(Note, cls).__setup__()
        cls._order = [('create_date', 'DESC')]
