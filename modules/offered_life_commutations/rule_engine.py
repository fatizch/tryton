# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = [
    'RuleRuntime',
    ]


class RuleRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_life_commutation(cls, args, table_code, rate, frequency, age, key):
        Manager = Pool().get('table.commutation_manager')
        values = Manager.get_life_commutation(table_code, rate, frequency, age)
        return values[key]
