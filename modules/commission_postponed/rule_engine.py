# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.rule_engine import check_args

__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('option', 'agent')
    def _re_contract_rank_on_period(cls, args, period_start_date,
            period_end_date):
        contract_id = args['contract'].id
        Contract = Pool().get('contract')
        contract = Contract(contract_id)
        period_contracts = [x.id for x in Contract.search([
                ('agent', '=', contract.agent),
                ['OR',
                    ('end_date', '>=', period_start_date),
                    ('end_date', '=', None),
                ],
                ('initial_start_date', '<=', period_end_date)],
            order=[('initial_start_date', 'ASC'), ('create_date', 'ASC')])]
        index = None
        try:
            index = period_contracts.index(contract_id)
            index += 1
        except ValueError:
            pass
        return index
