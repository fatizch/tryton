# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, utils
from trytond.modules.coog_core.coog_date import FREQUENCY_CONVERSION_TABLE

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    ]

ANNUAL_CONVERSION_TABLE = {
    'yearly': 1,
    'half_yearly': 2,
    'quaterly': 4,
    'monthly': 12,
    }


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


class ContractOption:
    __name__ = 'contract.option'

    annual_premium_incl_tax = fields.Function(
        fields.Numeric('Annual Premium Including Taxes',
            digits=(16, Eval('currency_digits', 2))),
        'get_premium')
    annual_premium_excl_tax = fields.Function(
        fields.Numeric('Annual Premium Excluding Taxes',
            digits=(16, Eval('currency_digits', 2))),
        'get_premium')
    annual_taxes = fields.Function(
        fields.Numeric('Annual Taxes',
            digits=(16, Eval('currency_digits', 2))),
        'get_premium')
    monthly_premium_incl_tax = fields.Function(
        fields.Numeric('Monthly Premium Including Taxes',
            digits=(16, Eval('currency_digits', 2))),
        'get_premium')
    monthly_premium_excl_tax = fields.Function(
        fields.Numeric('Monthly Premium Excluding Taxes',
            digits=(16, Eval('currency_digits', 2))),
        'get_premium')
    monthly_taxes = fields.Function(
        fields.Numeric('Monthly Taxes',
            digits=(16, Eval('currency_digits', 2))),
        'get_premium')

    def get_void_annual_premium_incl_tax(self):
        return Decimal('0.0')

    def get_void_annual_premium_excl_tax(self):
        return Decimal('0.0')

    def compute_premium_with_extra_premium(self, amount, extra_premiums):
        premium_amount = amount or Decimal('0.0')
        for extra_premium in extra_premiums:
            premium_amount += sum([x.amount for x in extra_premium.premiums], 0)
        return premium_amount

    @classmethod
    def get_premium(cls, options, names, date=None):
        annual_premiums_incl_tax = {o.id: Decimal('0.0') for o in options}
        annual_premiums_excl_tax = {o.id: Decimal('0.0') for o in options}
        annual_premiums_taxes = {o.id: Decimal('0.0') for o in options}
        monthly_premiums_incl_tax = {o.id: Decimal('0.0') for o in options}
        monthly_premiums_excl_tax = {o.id: Decimal('0.0') for o in options}
        monthly_premiums_taxes = {o.id: Decimal('0.0') for o in options}

        date = date or utils.today()
        for option in options:
            premiums = utils.get_good_versions_at_date(option, 'premiums', date,
                'start', 'end')
            extra_premiums = utils.get_good_versions_at_date(option,
                'extra_premiums', date, 'start', 'end')
            annual_premium_incl_tax = annual_premium_excl_tax = \
                monthly_premium_incl_tax = monthly_premium_excl_tax = \
                Decimal('0.0')
            if not premiums:
                annual_premium_incl_tax = option. \
                    get_void_annual_premium_incl_tax()
                annual_premium_excl_tax = option. \
                    get_void_annual_premium_excl_tax()
            else:
                premiums.sort(key=lambda x: x.start)
                last_premium = premiums[-1]
                Tax = Pool().get('account.tax')
                if last_premium.frequency in ['yearly', 'monthly', 'quaterly',
                        'half_yearly']:
                    annual_premium_incl_tax = option. \
                        compute_premium_with_extra_premium(last_premium.amount,
                            extra_premiums) * Decimal(
                                ANNUAL_CONVERSION_TABLE[last_premium.frequency])
                    annual_premium_excl_tax = option.currency.round(
                        Tax._reverse_unit_compute(annual_premium_incl_tax,
                            last_premium.taxes, date))
                if option.status != 'void' and option.start_date and \
                    option.start_date <= date <= (option.end_date or datetime.
                        date.max):
                    latest_premium = premiums[0]
                    if latest_premium.frequency in ['yearly', 'monthly',
                            'quaterly', 'half_yearly']:
                        monthly_premium_incl_tax = option. \
                            compute_premium_with_extra_premium(
                                latest_premium.amount, extra_premiums) / \
                            Decimal(FREQUENCY_CONVERSION_TABLE[
                                    latest_premium.frequency])
                        monthly_premium_excl_tax = option.currency.round(
                            Tax._reverse_unit_compute(monthly_premium_incl_tax,
                                latest_premium.taxes, date))

            annual_premiums_incl_tax[option.id] = annual_premium_incl_tax
            annual_premiums_excl_tax[option.id] = annual_premium_excl_tax
            annual_premiums_taxes[option.id] = annual_premium_incl_tax - \
                annual_premium_excl_tax
            monthly_premiums_incl_tax[option.id] = monthly_premium_incl_tax
            monthly_premiums_excl_tax[option.id] = monthly_premium_excl_tax
            monthly_premiums_taxes[option.id] = monthly_premium_incl_tax - \
                monthly_premium_excl_tax

        result = {
            'annual_premium_incl_tax': annual_premiums_incl_tax,
            'annual_premium_excl_tax': annual_premiums_excl_tax,
            'annual_taxes': annual_premiums_taxes,
            'monthly_premium_incl_tax': monthly_premiums_incl_tax,
            'monthly_premium_excl_tax': monthly_premiums_excl_tax,
            'monthly_taxes': monthly_premiums_taxes,
            }
        return {key: result[key] for key in names}
