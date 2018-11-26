# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.operators import Concat

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


class DsnMessage(metaclass=PoolMeta):
    __name__ = 'dsn.message'

    @classmethod
    def _get_origin(cls):
        res = super(DsnMessage, cls)._get_origin()
        return res + ['account.invoice']

    @classmethod
    def last_dsn_message_create_date(cls):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        dsn_message = cls.__table__()
        invoice = pool.get('account.invoice').__table__()
        cursor.execute(*dsn_message.join(invoice, condition=(
                    dsn_message.origin == Concat('account.invoice,',
                        invoice.id))
                ).select(dsn_message.create_date,
                where=(dsn_message.state == 'done') &
                    (invoice.business_kind == 'pasrau'),
                    order_by=dsn_message.create_date.desc,
                    limit=1
                ))
        slip_dates = cursor.fetchall()
        if slip_dates:
            return slip_dates[0]
