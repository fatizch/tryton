# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model

__all__ = ['add_premium_rules']


def add_premium_rules(product):
    Rule = Model.get('rule_engine')
    OptionDescriptionPremiumRule = Model.get(
        'offered.option.description.premium_rule')
    rules = Rule.find([('short_name', '=', 'simple_premium_rule')])
    if not rules:
        return product
    for coverage in product.coverages:
        premium_rule = OptionDescriptionPremiumRule(
                frequency='monthly',
                )
        premium_rule.rule_extra_data = {}
        premium_rule.rule = rules[0]
        premium_rule.rule_extra_data = {"premium_amount": {"decimal": "100",
                "__class__": "Decimal"}}
        coverage.premium_rules.append(premium_rule)
    return product
