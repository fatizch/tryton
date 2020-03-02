# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, utils
from trytond.modules.rule_engine import check_args

__all__ = [
    'RuleEngine',
    'Runtime',
    ]


class RuleEngine(metaclass=PoolMeta):
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection += [
            ('contract_extra_detail', 'Contract Extra Detail'),
            ]

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'contract_extra_detail':
            return 'dict'
        return super(RuleEngine, self).on_change_with_result_type(name)


class Runtime(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('contract')
    def _re_contract_extra_detail(cls, args, key, date):
        assert date
        contract = args['contract']
        extra_data = utils.get_value_at_date(contract.extra_datas, date)
        if extra_data is None:
            return None
        return (extra_data.extra_details or {}).get(key, None)
