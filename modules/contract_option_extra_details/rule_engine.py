# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields
from trytond.modules.rule_engine import check_args

__all__ = [
    'RuleEngine',
    'Runtime',
    ]


class RuleEngine:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection += [
            ('option_extra_detail', 'Option Extra Detail'),
            ]

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'option_extra_detail':
            return 'dict'
        return super(RuleEngine, self).on_change_with_result_type(name)


class Runtime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('option')
    def _re_option_extra_detail(cls, args, key, date):
        assert date
        option = args['option']
        return (option.get_version_at_date(date).extra_details or {}).get(key,
            None)

    @classmethod
    def _re_extra_details_computing_mode(cls, args):
        return args.get('_extra_details_mode', 'normal')
