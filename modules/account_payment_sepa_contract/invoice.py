# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    ]


class Invoice:
    __name__ = 'account.invoice'

    sepa_mandate = fields.Many2One('account.payment.sepa.mandate',
        'Sepa Mandate', states={'readonly': Eval('state') != 'draft'},
        ondelete='RESTRICT')
    bank_account = fields.Function(
        fields.Many2One('bank.account', 'Bank Account'),
        'get_bank_account')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._check_modify_exclude.append('sepa_mandate')

    def update_invoice_before_post(self):
        invoice = super(Invoice, self).update_invoice_before_post()
        if not self.contract:
            return invoice
        contract_revision_date = max(self.invoice_date, utils.today())
        with Transaction().set_context(
                contract_revision_date=contract_revision_date):
            if (self.contract.billing_information.direct_debit and
                    self.contract.billing_information.sepa_mandate):
                invoice['sepa_mandate'] = \
                    self.contract.billing_information.sepa_mandate
            else:
                invoice['sepa_mandate'] = None
            return invoice

    def get_bank_account(self, name):
        return (self.sepa_mandate.account_number.account.id
            if self.sepa_mandate else None)
