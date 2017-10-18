# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null, Literal

from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool

__all__ = [
    'Invoice',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.business_kind.selection += [
            ('wholesale_invoice', 'Wholesale Invoice'),
            ]

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        super(Invoice, cls).__register__(module_name)
        # Migration from 1.6 Store Business Kind
        cursor = Transaction().connection.cursor()
        invoice = cls.__table__()
        to_update = cls.__table__()
        insurer = pool.get('insurer').__table__()

        query = invoice.join(insurer,
            condition=invoice.party == insurer.party
            ).select(invoice.id,
            where=((invoice.business_kind == Null)
                & (invoice.type == 'out_invoice')))
        cursor.execute(*to_update.update(
                columns=[to_update.business_kind],
                values=[Literal('wholesale_invoice')],
                where=to_update.id.in_(query)))

    @classmethod
    def get_commission_invoice_types(cls):
        return super(Invoice, cls).get_commission_invoice_types() + [
            'wholesale_invoice']
