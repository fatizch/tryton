# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Len

from trytond.modules.coog_core import fields
from trytond.modules.rule_engine import get_rule_mixin


__all__ = [
    'OptionBenefit',
    ]


class OptionBenefit(get_rule_mixin('underwriting_rule', 'Underwriting Rule')):
    __metaclass__ = PoolMeta
    __name__ = 'contract.option.benefit'

    available_underwriting_rules = fields.Function(
        fields.Many2Many('rule_engine', None, None,
            'Available Underwriting Rules'),
        'get_available_rule')

    @classmethod
    def __setup__(cls):
        super(OptionBenefit, cls).__setup__()
        cls.underwriting_rule.domain = [
            ('id', 'in', Eval('available_underwriting_rules'))]
        cls.underwriting_rule.states['readonly'] = Len(
            'available_underwriting_rules') <= 1
        cls.underwriting_rule.depends = ['available_underwriting_rules']

    @fields.depends('benefit', 'available_underwriting_rules')
    def on_change_benefit(self):
        super(OptionBenefit, self).on_change_benefit()
        self.available_underwriting_rules = \
            self.get_available_rule('available_underwriting_rules')

    @classmethod
    def rule_fields(cls):
        return super(OptionBenefit, cls).rule_fields() + ['underwriting_rule']
