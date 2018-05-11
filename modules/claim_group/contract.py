# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If

from trytond.modules.coog_core import fields

__all__ = [
    'Contract',
    'Option',
    'CoveredElement',
    'TerminateContract',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    # TODO: move to claim_indemnification_group
    post_termination_claim_behaviour = fields.Selection([('', ''),
            ('stop_indemnifications', 'Stop Indemnifications'),
            ('lock_indemnifications', 'Lock Indemnifications'),
            ('normal_indemnifications', 'Normal Indemnifications'),
        ], 'Post Termination Claim Behaviour', readonly=True, states={
            'invisible':
            ~Eval('is_group') | ((Eval('status', '') != 'terminated')
                & ~Eval('post_termination_claim_behaviour')),
            'required':
            Eval('is_group') & (Eval('status', '') == 'terminated'),
            }, domain=[If(~Eval('is_group'),
                [('post_termination_claim_behaviour', 'in', (None, ''))],
                [])],
        depends=['is_group', 'status'])

    @classmethod
    def clean_before_reactivate(cls, contracts):
        cls.write(contracts, {'post_termination_claim_behaviour': ''})
        super(Contract, cls).clean_before_reactivate(contracts)


class Option:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option'

    previous_claims_management_rule = fields.Selection([
            ('no_management', 'No management'),
            ('full_management', 'Full management'),
            ('in_complement', 'In Complement of Previous Insurer')],
        'Previous Claims Management Rule',
        states={'invisible': ~Eval('is_group')}, depends=['is_group'])
    full_management_start_date = fields.Date('Full Management Start Date',
        states={'invisible': (
                Eval('previous_claims_management_rule') != 'full_management'),
            'required': Eval('previous_claims_management_rule') ==
            'full_management'},
        depends=['previous_claims_management_rule'])

    @classmethod
    def default_previous_claims_management_rule(cls):
        return 'no_management'


class CoveredElement:
    __metaclass__ = PoolMeta
    __name__ = 'contract.covered_element'

    def find_options_for_covered(self, at_date):
        res = super(CoveredElement, self).find_options_for_covered(at_date)
        return list(set(res +
                self.fill_list_with_previous_covered_options(at_date)))

    def fill_list_with_previous_covered_options(self, at_date):
        if self.manual_start_date and self.manual_start_date > at_date:
            return []
        if self.manual_end_date and self.manual_end_date < at_date:
            return []
        options = [option for option in self.options
            if (option.previous_claims_management_rule == 'full_management' and
                option.full_management_start_date <= at_date)]
        if not self.parent:
            return options
        return options + self.parent.fill_list_with_previous_covered_options(
            at_date)


class TerminateContract:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.terminate'

    is_group = fields.Boolean('Is Group', readonly=True)
    post_termination_claim_behaviour = fields.Selection([],
        'Post Termination Claim Behaviour', states={
            'invisible': ~Eval('is_group'),
            }, depends=['is_group'])

    @classmethod
    def __post_setup__(cls):
        Contract = Pool().get('contract')
        cls.post_termination_claim_behaviour.selection = list(
            Contract.post_termination_claim_behaviour.selection)
        super(TerminateContract, cls).__post_setup__()

    def step_default(self, name):
        defaults = super(TerminateContract, self).step_default(name)
        if 'contract' not in defaults:
            return defaults
        contracts = self._get_contracts()
        contract = Pool().get('contract')(defaults['contract'])
        values = getattr(contracts[contract.id], 'values', {})
        defaults['is_group'] = values.get('is_group', contract.is_group)
        defaults['post_termination_claim_behaviour'] = values.get(
            'post_termination_claim_behaviour',
            contract.product.default_termination_claim_behaviour)
        return defaults

    def step_update(self):
        super(TerminateContract, self).step_update()
        to_save = []
        for (_, contract_endorsement) in self._get_contracts().items():
            values = getattr(contract_endorsement, 'values', {})
            values['post_termination_claim_behaviour'] = \
                self.post_termination_claim_behaviour
            contract_endorsement.values = dict(values)
            to_save.append(contract_endorsement)
        Pool().get('endorsement.contract').save(to_save)
