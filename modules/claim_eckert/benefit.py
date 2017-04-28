# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, If

from trytond.modules.coog_core import fields

__all__ = [
    'Benefit',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    is_eckert = fields.Boolean('Apply Eckert Rules',
        states={'invisible': Eval('indemnification_kind') != 'capital'},
        help='If True, business rules defined in the French Eckert Law will '
        'be applied when creating services which use this benefit',
        depends=['indemnification_kind'])

    @classmethod
    def __setup__(cls):
        super(Benefit, cls).__setup__()
        cls.beneficiary_kind.domain = [If(~Eval('is_eckert'),
                cls.beneficiary_kind.domain,
                [('beneficiary_kind', '=', 'manual_list')])]
        cls.beneficiary_kind.depends += ['is_eckert']

    @fields.depends('indemnification_kind', 'is_eckert')
    def on_change_with_is_eckert(self):
        if self.indemnification_kind != 'capital':
            return False
        return self.is_eckert
