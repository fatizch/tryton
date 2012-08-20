#-*- coding:utf-8 -*-
from trytond.model import fields as fields

from trytond.modules.insurance_product import *
from trytond.modules.coop_utils import utils


__all__ = ['GroupInsurancePlan', 'GroupInsuranceCoverage',
           'GroupInsurancePlanOptionsCoverage', 'GroupBusinessRuleManager',
           'GroupGenericBusinessRule', 'GroupPricingRule',
           'GroupEligibilityRule', 'GroupBenefit', 'GroupBenefitRule',
           'GroupReserveRule', 'GroupCoverageAmountRule']


class GroupInsurancePlan(Product):
    'Group Insurance Plan'
    __name__ = 'ins_collective.product'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupInsurancePlan, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupInsuranceCoverage(Coverage):
    'Group Insurance Coverage'
    __name__ = 'ins_collective.coverage'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupInsuranceCoverage, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupInsurancePlanOptionsCoverage(ProductOptionsCoverage):
    'Define Group Insurance Plan - Coverage relations'
    __name__ = 'ins_collective.product-options-coverage'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupInsurancePlanOptionsCoverage, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupBusinessRuleManager(BusinessRuleManager):
    'Group Business Rule Manager'
    __name__ = 'ins_collective.business_rule_manager'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupBusinessRuleManager, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupGenericBusinessRule(GenericBusinessRule):
    'Group Generic Business Rule'
    __name__ = 'ins_collective.generic_business_rule'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupGenericBusinessRule, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupPricingRule(PricingRule):
    'Pricing Rule'
    __name__ = 'ins_collective.pricing_rule'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupPricingRule, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupEligibilityRule(EligibilityRule):
    'Eligibility Rule'
    __name__ = 'ins_collective.eligibility_rule'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupEligibilityRule, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupBenefit(Benefit):
    'Benefit'

    __name__ = 'ins_collective.benefit'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupBenefit, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupBenefitRule(BenefitRule):
    'Benefit Rule'

    __name__ = 'ins_collective.benefit_rule'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupBenefitRule, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupReserveRule(ReserveRule):
    'Reserve Rule'

    __name__ = 'ins_collective.reserve_rule'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupReserveRule, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupCoverageAmountRule(CoverageAmountRule):
    'Coverage Amount Rule'

    __name__ = 'ins_collective.coverage_amount_rule'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupCoverageAmountRule, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')

