#-*- coding:utf-8 -*-
from trytond.model import fields

from trytond.modules.insurance_product import product, business_rule, benefit
from trytond.modules.insurance_product import coverage, clause
from trytond.modules.insurance_product.benefit import *
from trytond.modules.insurance_product.business_rule import eligibility_rule
from trytond.modules.insurance_product.business_rule import benefit_rule
from trytond.modules.insurance_product.business_rule import reserve_rule
from trytond.modules.insurance_product.business_rule import \
    coverage_amount_rule
from trytond.modules.insurance_product.business_rule import clause_rule
from trytond.modules.insurance_product.business_rule import deductible_rule
from trytond.modules.insurance_product.business_rule import term_renewal_rule
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

    @classmethod
    def __setup__(cls):
        field = fields.One2Many('ins_collective.coverage',
            'product', 'Options')
        cls.options = field


class GroupInsuranceCoverage(GroupRoot, coverage.Coverage):
    'Group Insurance Coverage'

    __name__ = 'ins_collective.coverage'

    product = fields.Many2One('ins_collective.product', 'Product',
        ondelete='CASCADE')


class GroupBusinessRuleManager(GroupRoot, business_rule.BusinessRuleManager):
    'Group Business Rule Manager'

    __name__ = 'ins_collective.business_rule_manager'


class GroupGenericBusinessRule(GroupRoot, business_rule.GenericBusinessRule):
    'Group Generic Business Rule'

    __name__ = 'ins_collective.generic_business_rule'

    @classmethod
    def __setup__(cls):
        super(GroupGenericBusinessRule, cls).__setup__()


class GroupEligibilityRule(GroupRoot, eligibility_rule.EligibilityRule):
    'Eligibility Rule'

    __name__ = 'ins_collective.eligibility_rule'


class GroupEligibilityRelationKind(GroupRoot,
        eligibility_rule.EligibilityRelationKind):
    'Define relation between eligibility rule and relation kind authorized'

    __name__ = 'ins_collective.eligibility_relation_kind'


class GroupBenefit(GroupRoot, benefit.Benefit):
    'Benefit'

    __name__ = 'ins_collective.benefit'


class GroupBenefitRule(GroupRoot, benefit_rule.BenefitRule):
    'Benefit Rule'

    __name__ = 'ins_collective.benefit_rule'


class GroupReserveRule(GroupRoot, reserve_rule.ReserveRule):
    'Reserve Rule'

    __name__ = 'ins_collective.reserve_rule'


class GroupCoverageAmountRule(GroupRoot,
        coverage_amount_rule.CoverageAmountRule):
    'Coverage Amount Rule'

    __name__ = 'ins_collective.coverage_amount_rule'


class GroupClause(GroupRoot, clause.Clause):
    'Clause'

    __name__ = 'ins_collective.clause'


class GroupClauseVersion(GroupRoot, clause.ClauseVersion):
    'Clause Version'

    __name__ = 'ins_collective.clause_version'


class GroupClauseRule(GroupRoot, clause_rule.ClauseRule):
    'Clause Rule'

    __name__ = 'ins_collective.clause_rule'


class GroupDeductibleRule(GroupRoot, deductible_rule.DeductibleRule):
    'Deductible Rule'

    __name__ = 'ins_collective.deductible_rule'


class GroupClauseRelation(GroupRoot, clause_rule.ClauseRelation):
    'Relation between clause and offered'

    __name__ = 'ins_collective.clause_relation'


class GroupTermRenewalRule(GroupRoot, term_renewal_rule.TermRenewalRule):
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
