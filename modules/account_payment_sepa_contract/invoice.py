from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    ]


class Invoice:
    __name__ = 'account.invoice'

    sepa_mandate = fields.Many2One('account.payment.sepa.mandate',
        'Sepa Mandate', states={'readonly': Eval('state') != 'draft'},
        domain=[('party', '=', Eval('party'))], depends=['state', 'party'],
        ondelete='RESTRICT')

    def update_invoice_before_post(self):
        invoice = super(Invoice, self).update_invoice_before_post()
        if not self.contract:
            return invoice
        contract_revision_date = max(self.invoice_date, utils.today())
        with Transaction().set_context(
                contract_revision_date=contract_revision_date):
            if (not self.sepa_mandate and
                    self.contract.billing_information.direct_debit and
                    self.contract.billing_information.sepa_mandate):
                invoice['sepa_mandate'] = \
                    self.contract.billing_information.sepa_mandate
            return invoice
