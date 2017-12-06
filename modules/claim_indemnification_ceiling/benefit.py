# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'Benefit',
    'BenefitRule',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    def calculate_ceiling(self, service):
        rule = self.benefit_rules[0] if self.benefit_rules \
            else None
        if not rule or not rule.indemnification_ceiling_rule:
            return
        args = {}
        service.init_dict_for_rule_engine(args)
        return rule.calculate_indemnification_ceiling_rule(args)


class BenefitRule(
        get_rule_mixin('indemnification_ceiling_rule',
            'Indemnification Ceiling Rule')):

    __metaclass__ = PoolMeta
    __name__ = 'benefit.rule'

    @classmethod
    def __setup__(cls):
        super(BenefitRule, cls).__setup__()
        cls.indemnification_ceiling_rule.domain = [
            ('type_', '=', 'indemnification_ceiling')]
