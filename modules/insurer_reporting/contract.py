# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'CoveredElement',
    ]


class Contract:
    __metaclass__ = PoolMeta
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
        'get_first_not_null_invoice')
    last_paid_invoice = fields.Function(
        fields.Many2One('contract.invoice', 'Last Paid Invoice'),
        'get_last_paid_invoice')
    number_paid_premiums = fields.Function(
        fields.Integer('Number of Paid Premiums'),
        'get_number_paid_premiums')

    @classmethod
    def get_first_not_null_invoice(cls, contracts, name):
        res = {c.id: None for c in contracts}
        for contract in contracts:
            first_not_null_invoice = Pool().get('contract.invoice').search([
                    ('contract', '=', contract.id),
                    ('invoice.total_amount', '!=', 0)],
                order=[('start', 'ASC')], limit=1)
            if first_not_null_invoice:
                res[contract.id] = first_not_null_invoice[0].id
        return res

    @classmethod
    def get_last_paid_invoice(cls, contracts, name):
        res = {c.id: None for c in contracts}
        for contract in contracts:
            last_paid_invoice = Pool().get('contract.invoice').search([
                    ('contract', '=', contract.id),
                    ('invoice_state', '=', 'paid')],
                order=[('start', 'DESC')], limit=1)
            if last_paid_invoice:
                res[contract.id] = last_paid_invoice[0].id
        return res

    @classmethod
    def get_number_paid_premiums(cls, contracts, name):
        res = {c.id: 0 for c in contracts}
        for contract in contracts:
            res[contract.id] = Pool().get('contract.invoice').search_count([
                    ('contract', '=', contract.id),
                    ('invoice_state', '=', 'paid')])
        return res

    @classmethod
    def get_paid_amount(cls, contracts, names):
        paid_amounts_incl_tax = {c.id: Decimal('0.0') for c in contracts}
        paid_amounts_excl_tax = {c.id: Decimal('0.0') for c in contracts}
        paid_amounts_taxes = {c.id: Decimal('0.0') for c in contracts}

        for invoice in Pool().get('account.invoice').search([
                ('contract', 'in', [x.id for x in contracts]),
                ('state', '=', 'paid')]):
            paid_amounts_incl_tax[invoice.contract.id] += invoice.total_amount
            paid_amounts_excl_tax[invoice.contract.id] += invoice.untaxed_amount
            paid_amounts_taxes[invoice.contract.id] += invoice.tax_amount

        result = {
            'paid_amount_incl_tax': paid_amounts_incl_tax,
            'paid_amount_excl_tax': paid_amounts_excl_tax,
            'paid_amount_taxes': paid_amounts_taxes,
            }
        return {key: result[key] for key in names}


class CoveredElement:
    __metaclass__ = PoolMeta
    __name__ = 'contract.covered_element'

    def get_covered_element_options_premiums(self):
        option_dict_list = []
        if not self.options:
            return option_dict_list
        Option = Pool().get('contract.option')
        names = ['monthly_premium_excl_tax', 'monthly_premium_incl_tax',
            'monthly_taxes', 'annual_premium_excl_tax',
            'annual_premium_incl_tax', 'annual_taxes']
        premiums = Option.get_premium(list(self.options), names, None)
        for option in self.options:
            option_dict_list.append(
                {
                    'option': option,
                    'monthly_premium_excl_tax': premiums[
                        'monthly_premium_excl_tax'][option.id],
                    'monthly_premium_incl_tax': premiums[
                        'monthly_premium_incl_tax'][option.id],
                    'monthly_taxes': premiums['monthly_taxes'][option.id],
                    'annual_premium_excl_tax': premiums[
                        'annual_premium_excl_tax'][option.id],
                    'annual_premium_incl_tax': premiums[
                        'annual_premium_incl_tax'][option.id],
                    'annual_taxes': premiums['annual_taxes'][option.id],
                })
        return option_dict_list
