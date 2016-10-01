# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields


__metaclass__ = PoolMeta
__all__ = [
    'ModifyCoveredElement',
    'CoveredElementDisplayer',
    ]


class ModifyCoveredElement:
    __name__ = 'contract.covered_element.modify'

    possible_claim_bank_owners = fields.Many2Many('party.party', None, None,
        'Possible Claim Bank Accounts', readonly=True)

    @classmethod
    def __setup__(cls):
        super(ModifyCoveredElement, cls).__setup__()
        cls.current_covered.domain = [cls.current_covered.domain, ['OR',
                ('claim_bank_account', '=', None),
                ('claim_bank_account.owners', 'in',
                    Eval('possible_claim_bank_owners'))]]
        cls.current_covered.depends += ['possible_claim_bank_owners']

    @fields.depends('possible_claim_bank_owners')
    def on_change_current_parent(self):
        super(ModifyCoveredElement, self).on_change_current_parent()

    def update_contract(self):
        super(ModifyCoveredElement, self).update_contract()
        if not self.contract:
            return
        self.possible_claim_bank_owners = self.contract.parties

    def _update_nothing(self, new_covered_element, parent, per_id):
        super(ModifyCoveredElement, self)._update_nothing(new_covered_element,
            parent, per_id)
        CoveredElement = Pool().get('contract.covered_element')
        prev_covered = CoveredElement(new_covered_element.cur_covered_id)
        covered = per_id[new_covered_element.cur_covered_id]
        if covered.claim_specific_bank_account != \
                prev_covered.claim_specific_bank_account:
            covered.claim_specific_bank_account = \
                prev_covered.claim_specific_bank_account

    def _update_modified(self, new_covered_element, parent, per_id):
        super(ModifyCoveredElement, self)._update_modified(new_covered_element,
            parent, per_id)
        good_covered = per_id[new_covered_element.cur_covered_id]
        if (good_covered.claim_bank_account !=
                new_covered_element.claim_bank_account):
            if (good_covered.claim_default_bank_account ==
                    new_covered_element.claim_bank_account):
                good_covered.claim_specific_bank_account = None
            else:
                good_covered.claim_specific_bank_account = \
                    new_covered_element.claim_bank_account


class CoveredElementDisplayer:
    __name__ = 'contract.covered_element.modify.displayer'

    claim_bank_account = fields.Many2One('bank.account', 'Claim Bank Account')

    @fields.depends('action', 'claim_bank_account', 'cur_covered_id')
    def on_change_action(self):
        super(CoveredElementDisplayer, self).on_change_action()
        if self.cur_covered_id and self.action == 'nothing':
            self.claim_bank_account = Pool().get('contract.covered_element')(
                self.cur_covered_id).claim_bank_account

    @fields.depends('claim_bank_account')
    def on_change_extra_data(self):
        super(CoveredElementDisplayer, self).on_change_extra_data()

    @fields.depends('action', 'claim_bank_account', 'cur_covered_id',
        'effective_date', 'extra_data')
    def on_change_claim_bank_account(self):
        if self.check_modified():
            self.action = 'modified'
        else:
            self.action = 'nothing'

    def check_modified(self):
        result = super(CoveredElementDisplayer, self).check_modified()
        if result or not self.cur_covered_id:
            return result
        previous_account = Pool().get('contract.covered_element')(
            self.cur_covered_id).claim_bank_account
        return self.claim_bank_account != previous_account

    @classmethod
    def new_displayer(cls, covered_element, effective_date):
        displayer = super(CoveredElementDisplayer, cls).new_displayer(
            covered_element, effective_date)
        displayer.claim_bank_account = getattr(covered_element,
            'claim_specific_bank_account', None) or getattr(covered_element,
            'claim_default_bank_account', None)
        return displayer

    @classmethod
    def _covered_element_fields_to_extract(cls):
        result = super(CoveredElementDisplayer,
            cls)._covered_element_fields_to_extract()
        result['contract.covered_element'].append(
            'claim_specific_bank_account')
        return result
