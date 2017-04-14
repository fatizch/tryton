# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.tools import grouped_slice

from trytond.modules.coog_core import model, fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    'InvoiceLine',
    'ClaimInvoiceLineDetail',
    ]


class Invoice:
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.business_kind.selection.append(('claim_invoice', 'Claim Invoice'))

    @classmethod
    def cancel(cls, invoices):
        Indemnification = Pool().get('claim.indemnification')
        super(Invoice, cls).cancel(invoices)
        claim_invoices = [i for i in invoices if i.business_kind ==
            'claim_invoice']
        cancelled_indemnifications = []
        unpaid_indemnifications = []
        for invoice in claim_invoices:
            for detail in [d for l in invoice.lines for d in l.claim_details]:
                if detail.indemnification.status == 'cancelled':
                    cancelled_indemnifications.append(detail.indemnification)
                elif detail.indemnification.status == 'paid':
                    unpaid_indemnifications.append(detail.indemnification)
        cancelled_indemnifications = list(set(cancelled_indemnifications))
        unpaid_indemnifications = list(set(unpaid_indemnifications))
        if cancelled_indemnifications:
            Indemnification.write(cancelled_indemnifications,
                {'status': 'cancel_controlled'})
        if unpaid_indemnifications:
            Indemnification.write(unpaid_indemnifications,
                {'status': 'controlled'})

    def _get_tax_context(self):
        context = super(Invoice, self)._get_tax_context()
        if not getattr(self, 'contract', None):
            context['tax_included'] = True
        return context

    def _get_move_line(self, date, amount):
        line = super(Invoice, self)._get_move_line(date, amount)
        if (getattr(self, 'business_kind', None) == 'claim_invoice' and
                self.type == 'in' and self.total_amount > 0):
            line.payment_date = utils.today()
        return line


class InvoiceLine:
    __name__ = 'account.invoice.line'

    claim_details = fields.One2Many('account.invoice.line.claim_detail',
        'invoice_line', 'Claim Details', readonly=True, size=1)
    claim_detail = fields.Function(
        fields.Many2One('account.invoice.line.claim_detail', 'Claim Detail'),
        'get_claim_detail')

    @classmethod
    def get_claim_detail(cls, lines, name):
        result = {x.id: None for x in lines}
        cursor = Transaction().connection.cursor()
        detail_table = Pool().get(
            'account.invoice.line.claim_detail').__table__()

        for line_slice in grouped_slice(lines):
            cursor.execute(*detail_table.select(detail_table.invoice_line,
                    detail_table.id, where=detail_table.invoice_line.in_(
                        [x.id for x in line_slice])))

            result.update(dict(cursor.fetchall()))
        return result


class ClaimInvoiceLineDetail(model.CoogSQL, model.CoogView):
    'Claim Invoice Line Detail'

    __name__ = 'account.invoice.line.claim_detail'

    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        ondelete='CASCADE', readonly=True, required=True, select=True)
    indemnification = fields.Many2One('claim.indemnification',
        'Indemnification', required=True, ondelete='RESTRICT', select=True)
    claim = fields.Function(
        fields.Many2One('claim', 'Claim'),
        'get_claim', searcher='search_claim')
    service = fields.Function(
        fields.Many2One('claim.service', 'Services'),
        'get_service')

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')

        # Migration from 1.8 : Drop hardcoded claim and service columns
        handler = TableHandler(cls, module)
        to_migrate = handler.column_exist('claim')
        super(ClaimInvoiceLineDetail, cls).__register__(module)

        if to_migrate:
            handler = TableHandler(cls, module)
            handler.drop_column('claim')
            handler.drop_column('service')

    def get_claim(self, name):
        # All the fields are required, no checks required
        return self.indemnification.service.claim.id

    @classmethod
    def search_claim(cls, name, clause):
        return [('indemnification.service.loss.claim', clause[1], clause[2])]

    def get_service(self, name):
        return self.indemnification.service.id

    def get_rec_name(self, name):
        return self.indemnification.rec_name
