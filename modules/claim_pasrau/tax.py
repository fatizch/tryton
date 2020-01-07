# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields

__all__ = [
    'Invoice',
    'Tax',
    'MoveLine',
    'InvoiceTax',
    'InvoiceLineTax',
    ]


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    def _build_pasrau_dict(self):
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
        return pasrau_dict

    def _get_taxes(self):
        if self.business_kind == 'claim_invoice':
            pasrau_dict = ServerContext().get('pasrau_data')
            if not pasrau_dict:
                pasrau_dict = self._build_pasrau_dict()
            with ServerContext().set_context(pasrau_data=pasrau_dict):
                return super(Invoice, self)._get_taxes()
        return super(Invoice, self)._get_taxes()

    def get_move(self):
        if self.business_kind == 'claim_invoice':
            pasrau_dict = self._build_pasrau_dict()
            with ServerContext().set_context(pasrau_data=pasrau_dict):
                return super(Invoice, self).get_move()
        return super(Invoice, self).get_move()


class Tax(metaclass=PoolMeta):
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


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    pasrau_rates_info = fields.One2Many('account.move.line.pasrau.rate',
        'move_line', 'Pasrau Rates Information', readonly=True)


class InvoiceTax(metaclass=PoolMeta):
    __name__ = 'account.invoice.tax'

    def get_move_lines(self):
        lines = super(InvoiceTax, self).get_move_lines()
        pasrau_dict = ServerContext().get('pasrau_data')
        if pasrau_dict is not None:
            pasrau_rate = pasrau_dict.get(
                'pasrau_rate', None)
            if pasrau_rate is None:
                return lines
            MoveLinePasrauRate = Pool().get('account.move.line.pasrau.rate')
            line_pasrau_rate_obj = MoveLinePasrauRate()
            line_pasrau_rate_obj.pasrau_rate = pasrau_rate
            line_pasrau_rate_obj.pasrau_rate_business_id = pasrau_dict.get(
                'pasrau_rate_business_id', None)
            line_pasrau_rate_obj.pasrau_rate_kind = pasrau_dict.get(
                'pasrau_rate_kind', None)
            line_pasrau_rate_obj.pasrau_rate_region = pasrau_dict.get(
                'pasrau_rate_region', None)
            for line in lines:
                if self.tax.type == 'pasrau_rate':
                    line.pasrau_rates_info = (line_pasrau_rate_obj,)
        return lines


class InvoiceLineTax(metaclass=PoolMeta):
    __name__ = 'account.invoice.line-account.tax'

    def _tax_amount(self, name):
        if self.line.invoice.business_kind == 'claim_invoice':
            pasrau_dict = ServerContext().get('pasrau_data')
            if not pasrau_dict:
                pasrau_dict = self.line.invoice._build_pasrau_dict()
            with ServerContext().set_context(pasrau_data=pasrau_dict):
                return super()._tax_amount(name)
        return super()._tax_amount(name)
