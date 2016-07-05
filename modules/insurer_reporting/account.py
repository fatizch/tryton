# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    'InvoiceLine',
    ]


class Invoice:
    __name__ = 'account.invoice'

    report_commissions = fields.Function(
        fields.One2Many('commission', None, 'Commissions To Report'),
        'get_report_commissions')

    def get_report_commissions(self, name):
        good_lines = [x for x in self.lines if x.from_commissions and x.amount]
        commissions = [x for good_line in good_lines
            for x in good_line.from_commissions]
        commissions.sort(key=lambda x: x.commissioned_contract.id)
        commissions = [x.id for x in commissions]
        return commissions


class InvoiceLine:
    __name__ = 'account.invoice.line'

    tax_rate = fields.Function(
        fields.Numeric('Tax Rate', digits=(16, 2)), 'get_tax_rate')
    taxed_amount = fields.Function(
        fields.Numeric('Taxed Amount', digits=(16, 2)), 'get_taxed_amount')
    tax_amount = fields.Function(
        fields.Numeric('Tax Amount', digits=(16, 2)), 'get_tax_amount')

    def get_tax_rate(self, name):
        return sum([x.rate for x in self.taxes])

    def get_tax_amount(self, name):
        return sum([x['amount'] for x in self._get_taxes()])

    def get_taxed_amount(self, name):
        return self.tax_amount + self.amount
