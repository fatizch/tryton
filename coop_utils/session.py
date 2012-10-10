import datetime

from trytond.pool import PoolMeta
from trytond.tr import Transaction


class DateClass():
    '''Overriden ir.date class for more accurate date management'''

    __metaclass__ = PoolMeta

    __name__ = 'ir.date'

    @staticmethod
    def today():
        ctx_date = Transaction().context.get('client_defined_date')
        if ctx_date:
            return ctx_date
        else:
            return super(DateClass).today()

    @staticmethod
    def system_today():
        return datetime.date.today()
