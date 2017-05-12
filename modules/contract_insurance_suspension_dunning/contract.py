# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import defaultdict

from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import utils

__all__ = [
    'Contract',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    @classmethod
    def get_action_dunnings(cls, contracts, contract_action, active=True,
            to_date=None):
        res = defaultdict(list)
        if not contracts:
            return res
        to_date = to_date or utils.today()
        Dunning = Pool().get('account.dunning')
        dunnings = Dunning.search([
                ('contract', 'in', [c.id for c in contracts]),
                ('active', '=', active),
                ('line.maturity_date', '<=', to_date),
                ('level.contract_action', '=', contract_action),
                ], order=[('line.maturity_date', 'ASC')])
        for dunning in dunnings:
            res[dunning.contract].append(dunning)
        return res

    @classmethod
    def calculate_suspensions_from_date(cls, contracts):
        dunnings_per_contract = cls.get_action_dunnings(contracts, 'hold')
        res = {}
        for contract in contracts:
            dunnings = dunnings_per_contract[contract]
            dunning = dunnings[0] if dunnings else None
            # The dunning process date of the first active and "hold action"
            # dunning should be the start_date of the contract rights
            # suspension period
            if dunning and dunning.level.contract_action == 'hold':
                res[contract] = dunning.calculate_last_process_date()
            else:
                res[contract] = utils.today()
        return res
