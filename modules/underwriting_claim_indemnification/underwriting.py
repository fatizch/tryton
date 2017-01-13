# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__all__ = [
    'UnderwritingDecisionType',
    'UnderwritingResult',
    ]


class UnderwritingDecisionType:
    __metaclass__ = PoolMeta
    __name__ = 'underwriting.decision.type'

    reduction_percentage = fields.Numeric('Reduction Percentage',
        digits=(16, 2), domain=['OR', [('reduction_percentage', '=', None)],
            [('reduction_percentage', '>=', 0),
                ('reduction_percentage', '<=', 1)]],
        states={'invisible': Eval('decision') != 'reduce_indemnification',
            'required': Eval('decision') == 'reduce_indemnification'},
        depends=['decision'])

    @classmethod
    def __setup__(cls):
        super(UnderwritingDecisionType, cls).__setup__()
        cls.decision.selection += [
            ('block_indemnification', 'Block Indemnifications'),
            ('reduce_indemnification', 'Reduce Indemnifications'),
            ]

    @fields.depends('decision', 'reduction_percentage')
    def on_change_decision(self):
        if self.decision != 'reduce_indemnification':
            self.reduction_percentage = 0
        elif not self.reduction_percentage:
            self.reduction_percentage = Decimal('0.5')


class UnderwritingResult:
    __metaclass__ = PoolMeta
    __name__ = 'underwriting.result'

    last_indemnification_date = fields.Function(
        fields.Date('Last Indemnification Date', states={
                'invisible': ~Eval('service')}, depends=['service']),
        'on_change_with_last_indemnification_date')

    @fields.depends('service')
    def on_change_with_last_indemnification_date(self, name=None):
        if not self.service:
            return None
        return self.service.last_indemnification_date
