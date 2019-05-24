# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import fields

__all__ = [
    'Product',
    'OptionDescription',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    default_termination_claim_behaviour = fields.Selection([
            ('', ''),
            ('stop_indemnifications', 'Stop Indemnifications'),
            ('lock_indemnifications', 'Lock Indemnifications'),
            ('normal_indemnifications', 'Normal Indemnifications')],
        'Default Post Termination Claim Behaviour',
        help=' Define how claim indemnification will be computed once this '
        'option is terminated',
        states={'invisible': ~Eval('is_group'),
            'required': Bool(Eval('is_group'))},
        depends=['is_group'])

    @classmethod
    def _get_subscriber_benefit_kinds(cls):
        return super()._get_subscriber_benefit_kinds() | {
            'subscriber_then_covered'}


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.benefits.domain = [cls.benefits.domain,
            [('is_group', '=', Eval('is_group'))]]
        cls.benefits.depends.append('is_group')
