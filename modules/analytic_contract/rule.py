# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.offered.extra_data import with_extra_data

__all__ = [
    'Rule',
    ]


class Rule(with_extra_data(['contract', 'product', 'covered_element',
        'option']), metaclass=PoolMeta):
    __name__ = 'analytic_account.rule'

    @classmethod
    def __setup__(cls):
        super(Rule, cls).__setup__()
        cls.extra_data.domain += [('type_', '=', 'selection')]
        cls.extra_data.help = 'Extra data list used to filter move line based' \
            ' on contract, option, covered extra_data'

    def match(self, pattern):
        all_extra_data = {}
        if 'extra_data' in pattern:
            copy_pattern = pattern.copy()
            all_extra_data = copy_pattern.pop('extra_data')
        res = super(Rule, self).match(copy_pattern)
        if not res:
            return res
        for key, value in self.extra_data.items():
            if key not in all_extra_data or value != all_extra_data[key]:
                return False
        return True
