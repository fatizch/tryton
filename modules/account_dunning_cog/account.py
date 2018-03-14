# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    inactive_dunnings = fields.One2ManyDomain('account.dunning', 'line',
        'Inactive Dunnings', domain=[('active', '=', False)],
         target_not_required=True)

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls.dunnings.states['invisible'] = ~Eval('dunnings')
