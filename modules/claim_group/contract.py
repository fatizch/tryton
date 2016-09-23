# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If

from trytond.modules.cog_utils import fields

__all__ = [
    'Contract',
    'TerminateContract',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

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
                [('post_termination_claim_behaviour', '=', '')],
                [])],
        depends=['is_group', 'status'])


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
            'post_termination_claim_behaviour', '')
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
