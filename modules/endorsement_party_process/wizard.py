# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool, If

from trytond.modules.coog_core import fields

__all__ = [
    'AskNextEndorsementChoice',
    'AskNextEndorsement',
    ]


class AskNextEndorsementChoice(metaclass=PoolMeta):

    __name__ = 'endorsement.ask_next_endorsement.choice'

    possible_contracts = fields.Many2Many('contract', None, None,
        'Possible Contracts', states={'invisible': True})
    contracts = fields.Many2Many('contract', None, None, 'Contracts',
        domain=[If(Bool(Eval('possible_contracts', False)),
                [('id', 'in', Eval('possible_contracts'))],
                [])], depends=['possible_contracts'])


class AskNextEndorsement(metaclass=PoolMeta):

    __name__ = 'endorsement.ask_next_endorsement'

    def default_choice(self, name):
        res = super().default_choice(name)
        endorsement = self.get_endorsement()
        next_endorsement_contracts = [x.id
            for x in endorsement.get_next_endorsement_contracts()]
        res['contracts'] = next_endorsement_contracts
        res['possible_contracts'] = next_endorsement_contracts
        return res

    def transition_apply_with_generate(self):
        with ServerContext().set_context(force_contracts_to_endorse=True,
                contracts_to_endorse=self.choice.contracts):
            with Transaction().set_context(force_synchronous=True):
                Pool().get('endorsement').apply([self.get_endorsement()])
                return 'end'
        return super().transition_apply_with_generate()
