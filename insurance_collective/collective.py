#-*- coding:utf-8 -*-

from trytond.modules.insurance_product import product, business_rule
from trytond.modules.insurance_product import coverage, clause
from trytond.modules.insurance_product.benefit import *
from trytond.modules.insurance_product.business_rule import pricing
from trytond.modules.insurance_product.business_rule import eligibility
from trytond.modules.insurance_product.business_rule import benefit, reserve
from trytond.modules.insurance_product.business_rule import coverage_amount
from trytond.modules.insurance_product.business_rule import clause as clause_r
from trytond.modules.insurance_product.business_rule import term_renewal
from trytond.modules.insurance_product import dynamic_data
from trytond.modules.coop_utils import utils


class GroupRoot(object):

    @classmethod
    def __setup__(cls):
        cls._table = None
        utils.change_relation_links(cls, 'ins_product', 'ins_collective')
        super(GroupRoot, cls).__setup__()


class GroupInsurancePlan(GroupRoot, product.Product):
    'Group Insurance Plan'

    __name__ = 'ins_collective.product'


class GroupInsuranceCoverage(GroupRoot, coverage.Coverage):
    'Group Insurance Coverage'

    __name__ = 'ins_collective.coverage'


class GroupInsurancePlanOptionsCoverage(GroupRoot,
        product.ProductOptionsCoverage):
    'Define Group Insurance Plan - Coverage relations'

    __name__ = 'ins_collective.product-options-coverage'


class GroupBusinessRuleManager(GroupRoot, business_rule.BusinessRuleManager):
    'Group Business Rule Manager'

    __name__ = 'ins_collective.business_rule_manager'


class GroupGenericBusinessRule(GroupRoot, business_rule.GenericBusinessRule):
    'Group Generic Business Rule'

    __name__ = 'ins_collective.generic_business_rule'


class GroupPricingData(GroupRoot, pricing.PricingData):
    'Pricing Data'

    __name__ = 'ins_collective.pricing_data'


class GroupPriceCalculator(GroupRoot, pricing.PriceCalculator):
    'Price Calculator'

    __name__ = 'ins_collective.pricing_calculator'


class GroupPricingRule(GroupRoot, pricing.PricingRule):
    'Pricing Rule'

    __name__ = 'ins_collective.pricing_rule'


class GroupEligibilityRule(GroupRoot, eligibility.EligibilityRule):
    'Eligibility Rule'

    __name__ = 'ins_collective.eligibility_rule'


class GroupEligibilityRelationKind(GroupRoot,
        eligibility.EligibilityRelationKind):
    'Define relation between eligibility rule and relation kind authorized'

    __name__ = 'ins_collective.eligibility_relation_kind'


class GroupBenefit(GroupRoot, Benefit):
    'Benefit'

    __name__ = 'ins_collective.benefit'


class GroupBenefitRule(GroupRoot, benefit.BenefitRule):
    'Benefit Rule'

    __name__ = 'ins_collective.benefit_rule'


class GroupReserveRule(GroupRoot, reserve.ReserveRule):
    'Reserve Rule'

    __name__ = 'ins_collective.reserve_rule'


class GroupCoverageAmountRule(GroupRoot, coverage_amount.CoverageAmountRule):
    'Coverage Amount Rule'

    __name__ = 'ins_collective.coverage_amount_rule'


class GroupClause(GroupRoot, clause.Clause):
    'Clause'

    __name__ = 'ins_collective.clause'


class GroupClauseVersion(GroupRoot, clause.ClauseVersion):
    'Clause Version'

    __name__ = 'ins_collective.clause_version'


class GroupClauseRule(GroupRoot, clause_r.ClauseRule):
    'Clause Rule'

    __name__ = 'ins_collective.clause_rule'


class GroupClauseRelation(GroupRoot, clause_r.ClauseRelation):
    'Relation between clause and offered'

    __name__ = 'ins_collective.clause_relation'


class GroupTermRenewalRule(GroupRoot, term_renewal.TermRenewalRule):
    'Clause Rule'

    __name__ = 'ins_collective.term_renewal_rule'


class GroupSchemaElement(GroupRoot, dynamic_data.CoopSchemaElement):
    'Dynamic Data Definition'

    __name__ = 'ins_collective.schema_element'


class GroupSchemaElementRelation(GroupRoot,
        dynamic_data.SchemaElementRelation):
    'Relation between schema element and dynamic data manager'

    __name__ = 'ins_collective.schema_element_relation'


class GroupDynamicDataManager(GroupRoot, dynamic_data.DynamicDataManager):
    'Dynamic Data Manager'

    __name__ = 'ins_collective.dynamic_data_manager'
