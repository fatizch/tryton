# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

__all__ = [
    'OptionDescription',
    ]


class OptionDescription:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.benefits.domain = [cls.benefits.domain,
            [('is_group', '=', Eval('is_group'))]]
        cls.benefits.depends.append('is_group')
