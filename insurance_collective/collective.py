#-*- coding:utf-8 -*-
from trytond.modules.insurance_product import *
from trytond.modules.coop_utils import utils


__all__ = ['GroupInsurancePlan', 'GroupInsuranceCoverage',
           'GroupInsurancePlanOptionsCoverage', 'GroupBusinessRuleManager',
           'GroupGenericBusinessRule', 'GroupPricingRule',
           'GroupPricingData', 'GroupPriceCalculator',
           'GroupEligibilityRule', 'GroupEligibilityRelationKind',
           'GroupBenefit', 'GroupBenefitRule',
           'GroupReserveRule', 'GroupCoverageAmountRule',
           'GroupClauseRule', 'GroupTermRenewalRule',
           'GroupSchemaElement', 'GroupSchemaElementRelation',
           'GroupDynamicDataManager']


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


class GroupPricingData(PricingData):
    'Pricing Rule'
    __name__ = 'ins_collective.pricing_data'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupPricingData, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupPriceCalculator(PriceCalculator):
    'Pricing Rule'
    __name__ = 'ins_collective.pricing_calculator'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupPriceCalculator, cls).__setup__()
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


class GroupEligibilityRelationKind(EligibilityRelationKind):
    'Define relation between eligibility rule and relation kind authorized'

    __name__ = 'ins_collective.eligibility_relation_kind'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupEligibilityRelationKind, cls).__setup__()
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


class GroupClauseRule(ClauseRule):
    'Clause Rule'

    __name__ = 'ins_collective.clause_rule'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupClauseRule, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupTermRenewalRule(ClauseRule):
    'Clause Rule'

    __name__ = 'ins_collective.term_renewal_rule'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupTermRenewalRule, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupSchemaElement(CoopSchemaElement):
    'Dynamic Data Definition'
    __name__ = 'ins_collective.schema_element'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupSchemaElement, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupSchemaElementRelation(SchemaElementRelation):
    'Relation between schema element and dynamic data manager'

    __name__ = 'ins_collective.schema_element_relation'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupSchemaElementRelation, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')


class GroupDynamicDataManager(DynamicDataManager):
    'Dynamic Data Manager'

    __name__ = 'ins_collective.dynamic_data_manager'
    _table = None

    @classmethod
    def __setup__(cls):
        super(GroupDynamicDataManager, cls).__setup__()
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')
