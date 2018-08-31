# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    import pytz
except ImportError:
    pytz = None

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__all__ = [
    'Sequence',
    'SequenceStrict',
    'Date',
    ]


class Sequence:
    __metaclass__ = PoolMeta
    __name__ = 'ir.sequence'

    @classmethod
    def _export_light(cls):
        return super(Sequence, cls)._export_light() | {'company'}


class SequenceStrict:
    __metaclass__ = PoolMeta
    __name__ = 'ir.sequence.strict'

    @classmethod
    def _export_light(cls):
        return super(SequenceStrict, cls)._export_light() | {'company'}


class Date:
    __metaclass__ = PoolMeta
    __name__ = 'ir.date'

    @classmethod
    def today(cls, timezone=None):
        '''
            Improve performance of tryton's company module override, which
            checks for the company's timezone if the value is not forced in the
            parameters.

            When calling the 'today' method a lot in the same transaction, the
            total time may be rather long (~1 sec per 10000 calls), so this
            methods caches the company's timezone in the transaction to avoid
            instantiating and reading the company's field more than once.
        '''
        if timezone or not pytz:
            return super(Date, cls).today(timezone=timezone)
        transaction = Transaction()
        transaction_tz = getattr(transaction, '_company_timezone', None)
        if transaction_tz:
            return super(Date, cls).today(timezone=transaction_tz)
        company_id = transaction.context.get('company')
        if company_id:
            company = Pool().get('company.company')(company_id)
            if company.timezone:
                transaction._company_timezone = pytz.timezone(company.timezone)
            else:
                transaction._company_timezone = None
        else:
            transaction._company_timezone = None
        return super(Date, cls).today(timezone=transaction._company_timezone)
