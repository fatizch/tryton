from trytond.pool import PoolMeta
from trytond.modules.cog_utils import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    'InvoiceLine',
    'ClaimInvoiceLineDetail',
    ]


class Invoice:
    __name__ = 'account.invoice'

    def _get_tax_context(self):
        context = super(Invoice, self)._get_tax_context()
        if not getattr(self, 'contract', None):
            context['tax_included'] = True
        return context


class InvoiceLine:
    __name__ = 'account.invoice.line'

    claim_details = fields.One2Many('account.invoice.line.claim_detail',
        'invoice_line', 'Claim Details', readonly=True, size=1)


class ClaimInvoiceLineDetail(model.CoopSQL, model.CoopView):
    'Claim Invoice Line Detail'

    __name__ = 'account.invoice.line.claim_detail'

    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        ondelete='CASCADE', readonly=True, required=True, select=True)
    claim = fields.Many2One('claim', 'Claim')
    service = fields.Many2One('claim.service', 'Services',
        ondelete='RESTRICT')
    indemnification = fields.Many2One('claim.indemnification',
        'Indemnification')
