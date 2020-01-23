# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import fields, coog_string

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

    def get_documentation_structure(self):
        doc = super(Product, self).get_documentation_structure()
        if self.is_group:
            doc['parameters'].append(
                coog_string.doc_for_field(self,
                    'default_termination_claim_behaviour'))
        return doc


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.benefits.domain = [cls.benefits.domain,
            [('is_group', '=', Eval('is_group'))]]
        cls.benefits.depends.append('is_group')
