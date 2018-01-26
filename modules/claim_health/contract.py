# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import utils, fields

__metaclass__ = PoolMeta
__all__ = [
    'CoveredElement',
    ]


class CoveredElement:
    __metaclass__ = PoolMeta
    __name__ = 'contract.covered_element'

    claim_bank_account = fields.Function(
        fields.Many2One('bank.account', 'Claim Bank Account'),
        'get_claim_bank_account')
    claim_default_bank_account = fields.Function(
        fields.Many2One('bank.account', 'Claim Default Bank Account'),
        'get_claim_default_bank_account')
    claim_specific_bank_account = fields.Many2One('bank.account',
        'Specific Claim Bank Account', ondelete='RESTRICT',
        domain=[('id', 'in', Eval('possible_claim_bank_accounts'))],
        depends=['possible_claim_bank_accounts'])
    possible_claim_bank_accounts = fields.Function(
        fields.Many2Many('bank.account', None, None,
            'Possible Claim Bank Account'),
        'get_possible_claim_bank_accounts')

    def get_claim_bank_account(self, name=None):
        if self.claim_specific_bank_account:
            return self.claim_specific_bank_account.id
        if self.claim_default_bank_account:
            return self.claim_default_bank_account.id

    def get_possible_claim_bank_accounts(self, name=None):
        res = []
        for party in self.contract.parties:
            res.extend([account.id for account in party.bank_accounts])
        return res

    def get_claim_default_bank_account(self, name=None):
        account = self.contract.subscriber.get_bank_account(utils.today())
        if account:
            return account.id
        if utils.is_module_installed('contract_insurance_invoice'):
            billing_info = self.contract.billing_information
            if billing_info and billing_info.direct_debit_account:
                return billing_info.direct_debit_account
