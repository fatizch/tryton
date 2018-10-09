# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta
from trytond.server_context import ServerContext

__all__ = [
    'Invoice',
    'InvoiceLine',
    'Tax',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    def _get_taxes(self):
        if self.business_kind == 'claim_invoice':
            pasrau_dict = {}
            pasrau_dict['party'] = self.party
            details = [x.claim_detail for x in self.lines]
            pasrau_dict['period_start'] = min(
                [x.indemnification.start_date for x in details
                    if x.indemnification.start_date] +
                [datetime.date.max])
            pasrau_dict['period_end'] = max(
                [x.indemnification.end_date for x in details
                    if x.indemnification.end_date] +
                [datetime.date.min])
            pasrau_dict['income'] = sum([
                    x.indemnification.amount
                    for x in details] or [])
            pasrau_dict['invoice_date'] = self.tax_date
            with ServerContext().set_context(pasrau_data=pasrau_dict):
                return super(Invoice, self)._get_taxes()
        return super(Invoice, self)._get_taxes()


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'

    def _get_taxes(self):
        if self.invoice.business_kind == 'claim_invoice':
            pasrau_dict = {}
            pasrau_dict['party'] = self.party
            pasrau_dict['period_start'] = (
                self.claim_detail.indemnification.start_date or
                datetime.date.max)
            pasrau_dict['period_end'] = (
                self.claim_detail.indemnification.end_date or
                datetime.date.min)
            pasrau_dict['income'] = self.claim_detail.indemnification.amount
            pasrau_dict['invoice_date'] = self.tax_date
            with ServerContext().set_context(pasrau_data=pasrau_dict):
                return super(InvoiceLine, self)._get_taxes()
        return super(InvoiceLine, self)._get_taxes()


class Tax:
    __metaclass__ = PoolMeta
    __name__ = 'account.tax'

    @classmethod
    def __setup__(cls):
        super(Tax, cls).__setup__()
        cls.type.selection.append(
            ('pasrau_rate', 'Pasrau Rate'))

    def _process_tax(self, price_unit):
        if self.type == 'pasrau_rate':
            pasrau_dict = ServerContext().get('pasrau_data')
            party = pasrau_dict.get('party')
            period_start = pasrau_dict.get('period_start')
            period_end = pasrau_dict.get('period_end')
            income = pasrau_dict.get('income')
            invoice_date = pasrau_dict.get('invoice_date')
            rate = -party.get_appliable_pasrau_rate(income, period_start,
                period_end, invoice_date)
            amount = price_unit * rate
            return {
                'base': price_unit,
                'amount': amount,
                'tax': self,
            }
        return super(Tax, self)._process_tax(price_unit)

    def _reverse_rate_amount_from_type(self):
        if self.type == 'pasrau_rate':
            pasrau_dict = ServerContext().get('pasrau_data')
            party = pasrau_dict.get('party')
            period_start = pasrau_dict.get('period_start')
            period_end = pasrau_dict.get('period_end')
            income = pasrau_dict.get('income')
            invoice_date = pasrau_dict.get('invoice_date')
            rate = party.get_appliable_pasrau_rate(income, period_start,
                period_end, invoice_date)
            return -rate, 0
        return super(Tax, self)._reverse_rate_amount_from_type()
