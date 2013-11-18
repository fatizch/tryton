import datetime

from trytond.pool import PoolMeta
from trytond.transaction import Transaction


__all__ = [
    'DateClass',
]


class DateClass():
    '''Overriden ir.date class for more accurate date management'''

    __metaclass__ = PoolMeta

    __name__ = 'ir.date'

    @classmethod
    def today(cls, timezone=None):
        ctx_date = Transaction().context.get('client_defined_date')
        if ctx_date:
            return ctx_date
        else:
            return super(DateClass, cls).today(timezone=timezone)

    @staticmethod
    def system_today():
        return datetime.date.today()
