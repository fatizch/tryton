# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast
from sql.operators import Concat

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval, In, Not, Or


__all__ = [
    'Invoice',
    'InvoiceLine',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._error_messages.update({
                'batch_claims_paid': 'Claims Paid',
                })
        cls.business_kind.selection += [
            ('claim_insurer_invoice', 'Claim Insurer Invoice'),
            ]

    @classmethod
    def get_claim_invoice_types(cls):
        return ['claim_insurer_invoice']

    @classmethod
    def get_commission_insurer_invoice_types(cls):
        return super(Invoice, cls).get_commission_insurer_invoice_types() + [
            'claim_insurer_invoice']

    @classmethod
    def get_invoice_lines_for_reporting(cls, invoice_id):
        cursor = Transaction().connection.cursor()
        pool = Pool()
        invoice = cls.__table__()
        invoice_line = pool.get('account.invoice.line').__table__()
        invoice_line2 = pool.get('account.invoice.line').__table__()
        move_line = pool.get('account.move.line').__table__()
        move = pool.get('account.move').__table__()

        sub_query = invoice_line.join(move_line,
                condition=(invoice_line.id == move_line.principal_invoice_line)
            ).select(move_line.id,
            where=(invoice_line.invoice == invoice_id))

        query = invoice_line2.join(invoice,
            condition=(invoice_line2.invoice == invoice.id)
            ).join(move,
            condition=(move.origin == Concat('account.invoice,',
                    Cast(invoice.id, 'VARCHAR')))
            ).join(move_line,
            condition=(move_line.move == move.id)
            ).select(invoice_line2.id,
                where=(move_line.id.in_(sub_query))
                & (invoice.business_kind == 'claim_invoice'))

        cursor.execute(*query)
        res_set = {x for x, in cursor.fetchall()}
        res_list = list(res_set)
        InvoiceLine = pool.get('account.invoice.line')
        invoices = InvoiceLine.search([('id', 'in', res_list)])
        return invoices

    @classmethod
    def view_attributes(cls):
        is_claim_type = In(Eval('business_kind'),
            cls.get_claim_invoice_types())
        attributes = []
        for path, attr, state in super(Invoice, cls).view_attributes():
            if path == '//group[@id="invoice_lines"]' and attr == 'states':
                state = {
                    'invisible': Or(state['invisible'], is_claim_type),
                    }
            if (path == '//group[@id="invoice_lines_commission"]'
                    and attr == 'states'):
                state = {
                    'invisible': Or(state['invisible'], is_claim_type),
                    }
            attributes.append((path, attr, state))
        return attributes + [
            ('//group[@id="invoice_lines_claim"]',
                'states', {
                    'invisible': Not(is_claim_type),
                    })
            ]


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'

    @classmethod
    def view_attributes(cls):
        return super(InvoiceLine, cls).view_attributes() + [(
                '/form/notebook/page[@id="commissions"]',
                'states', {
                    'invisible': Eval('invoice_business_kind') ==
                    'claim_insurer_invoice'
                    }), (
                '/form/notebook/page[@id="benefits"]',
                'states', {
                    'invisible': Eval('invoice_business_kind') !=
                    'claim_insurer_invoice'
                    }),
            ]
