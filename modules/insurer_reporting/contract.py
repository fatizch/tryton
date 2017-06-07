# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    paid_amount_incl_tax = fields.Function(
        fields.Numeric('Paid Amount Including Tax'),
        'get_paid_amount')
    paid_amount_excl_tax = fields.Function(
        fields.Numeric('Paid Amount Excluding Tax'),
        'get_paid_amount')
    paid_amount_taxes = fields.Function(
        fields.Numeric('Paid Amount Taxes'),
        'get_paid_amount')
    first_not_null_invoice = fields.Function(
        fields.Many2One('contract.invoice', 'First Not Null Invoice'),
        'get_insurer_report_invoice')
    last_paid_invoice = fields.Function(
        fields.Many2One('contract.invoice', 'Last Paid Invoice'),
        'get_insurer_report_invoice')
    number_paid_premiums = fields.Function(
        fields.Integer('Number of Paid Premiums'),
        'get_insurer_report_invoice')

    @classmethod
    def get_insurer_report_invoice(cls, contracts, names):
        first_not_null_invoices = {c.id: None for c in contracts}
        last_paid_invoices = {c.id: None for c in contracts}
        numbers_paid_invoices = {c.id: 0 for c in contracts}

        for contract in contracts:
            first_not_null_invoice = last_paid_invoice = None
            number_paid_invoices = 0
            sorted_not_null_invoices = sorted([x for x in contract.invoices if
                    x.invoice.total_amount != 0], key=lambda k: k.invoice.start)
            if sorted_not_null_invoices:
                first_not_null_invoice = sorted_not_null_invoices[0]
                paid_invoices = [x for x in sorted_not_null_invoices
                    if x.invoice.state == 'paid']
                if paid_invoices:
                    last_paid_invoice = paid_invoices[-1]
                    number_paid_invoices = len(paid_invoices)

            first_not_null_invoices[contract.id] = first_not_null_invoice
            last_paid_invoices[contract.id] = last_paid_invoice
            numbers_paid_invoices[contract.id] = number_paid_invoices

        result = {
            'first_not_null_invoice': first_not_null_invoices,
            'last_paid_invoice': last_paid_invoices,
            'number_paid_premiums': numbers_paid_invoices,
            }
        return {key: result[key] for key in names}

    @classmethod
    def get_paid_amount(cls, contracts, names):
        paid_amounts_incl_tax = {c.id: Decimal('0.0') for c in contracts}
        paid_amounts_excl_tax = {c.id: Decimal('0.0') for c in contracts}
        paid_amounts_taxes = {c.id: Decimal('0.0') for c in contracts}
        for contract in contracts:
            paid_amounts = [(x.invoice.total_amount, x.invoice.untaxed_amount,
                    x.invoice.tax_amount) for x in contract.invoices
                if x.invoice_state == 'paid']
            if paid_amounts:
                paid_amount_incl_tax, paid_amount_excl_tax, paid_amount_taxes \
                    = [sum(x, 0) for x in zip(*paid_amounts)]
                paid_amounts_incl_tax[contract.id] = paid_amount_incl_tax
                paid_amounts_excl_tax[contract.id] = paid_amount_excl_tax
                paid_amounts_taxes[contract.id] = paid_amount_taxes

        result = {
            'paid_amount_incl_tax': paid_amounts_incl_tax,
            'paid_amount_excl_tax': paid_amounts_excl_tax,
            'paid_amount_taxes': paid_amounts_taxes,
            }
        return {key: result[key] for key in names}
