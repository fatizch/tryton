# -*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

STATE_LIFE = (
    Eval('_parent_offered', {}).get('family') != 'life')

__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    ]


class OptionDescription:
    __name__ = 'offered.option.description'

    coverage_amount_rules = fields.One2Many('offered.coverage_amount.rule',
        'offered', 'Coverage Amount Rules',
        states={'invisible': Eval('family') != 'life'}, delete_missing=True)
    is_coverage_amount_needed = fields.Function(
        fields.Boolean('Coverage Amount Needed', states={'invisible': True}),
        'get_is_coverage_amount_needed')

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.family.selection.append(('life', 'Life'))
        cls.insurance_kind.selection.extend([
                ('temporary_disability', 'Temporary Disability'),
                ('partial_disability', 'Partial Disability'),
                ('total_disability', 'Total Disability'),
                ('total_autonomy_loss',
                    'Total And Irreversible Autonomy Loss'),
                ('death', 'Death'),
                ])

    @classmethod
    def view_attributes(cls):
        return super(OptionDescription, cls).view_attributes() + [
            ('/form/notebook/page[@id="managers"]/notebook'
                '/page[@id="coverage_amount"]',
                'states', {'invisible': Eval('family') != 'life'}),
            ]

    def get_is_coverage_amount_needed(self, name=None):
        return self.family == 'life'
