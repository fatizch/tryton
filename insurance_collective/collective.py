#-*- coding:utf-8 -*-
import copy

from trytond.model import fields
from trytond.pyson import Eval

from trytond.modules.insurance_product import product, benefit
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
from trytond.modules.insurance_product import complementary_data
from trytond.modules.coop_utils import utils
from trytond.modules.insurance_product.business_rule import pricing_rule

IND_TO_COLL = {
    'ins_product.benefit': 'ins_collective.benefit',
    'ins_product.benefit_rule': 'ins_collective.benefit_rule',
    'ins_product.clause': 'ins_collective.clause',
    'ins_product.clause_relation': 'ins_collective.clause_relation',
    'ins_product.clause_rule': 'ins_collective.clause_rule',
    'ins_product.clause_version': 'ins_collective.clause_version',
    'ins_product.coverage': 'ins_collective.coverage',
    'ins_product.coverage_amount_rule': 'ins_collective.coverage_amount_rule',
    'ins_product.deductible_rule': 'ins_collective.deductible_rule',
    'ins_product.complementary_data_manager': 'ins_collective.complementary_data_manager',
    'ins_product.eligibility_relation_kind':\
        'ins_collective.eligibility_relation_kind',
    'ins_product.eligibility_rule': 'ins_collective.eligibility_rule',
    'ins_product.pricing_component': 'ins_collective.pricing_component',
    'ins_product.pricing_rule': 'ins_collective.pricing_rule',
    'ins_product.product': 'ins_collective.product',
    'ins_product.reserve_rule': 'ins_collective.reserve_rule',
    'ins_product.schema_element': 'ins_collective.schema_element',
    'ins_product.schema_element_relation':\
        'ins_collective.schema_element_relation',
    'ins_product.term_renewal_rule': 'ins_collective.term_renewal_rule',

    'ins_contract.contract': 'ins_collective.enrollment',
    'ins_contract.option': 'ins_collective.option',
    'ins_product.package-coverage': 'ins_collective.package-coverage',
    'ins_product.product-item_desc': 'ins_collective.product-item_desc',
}


class GroupRoot(object):

    @classmethod
    def __setup__(cls):
        cls._table = None

        utils.change_relation_links(cls, convert_dict=IND_TO_COLL)
        super(GroupRoot, cls).__setup__()


class GroupInsurancePlan(GroupRoot, product.Product):
    'Group Insurance Plan'

    __name__ = 'ins_collective.product'

    contract = fields.Many2One('ins_collective.gbp_contract', 'Contract',
        ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(GroupInsurancePlan, cls).__setup__()
        field = fields.One2Many('ins_collective.coverage',
            'product', 'Options')
        cls.options = field

        cls.contract_generator = copy.copy(cls.contract_generator)
        cls.contract_generator.required = False
        cls.contract_generator.states['required'] = ~Eval('template')
        cls.contract_generator.depends = ['template']

        cls.template = copy.copy(cls.template)
        cls.template.on_change = ['template', 'options', 'start_date']

        cls.code = copy.copy(cls.code)

    def on_change_template(self):
        res = super(GroupInsurancePlan, self).on_change_template()
        if not self.template:
            res['options'] = []
        else:
            res['code'] = self.template.code
            res['name'] = self.template.name
            options = []
            for option in self.template.options:
                clone_option = utils.create_inst_with_default_val(
                    self.__class__, 'options')[0]
                clone_option['code'] = option.code
                clone_option['name'] = option.name
                clone_option['template'] = option.id
                if option.family:
                    clone_option['family'] = option.family
                clone_option['is_package'] = option.is_package
                #pricing_rules = {'add', [{'start_date': self.start_date}]}
                #clone_option['pricing_mgr'] = [{}]
#                benefits = []
#                for benefit in option.benefits:
#                    clone_benefit = utils.create_inst_with_default_val(
#                        option.__class__, 'benefits')[0]
#                    clone_benefit['code'] = benefit.code
#                    clone_benefit['name'] = benefit.name
#                    clone_benefit['template'] = benefit.id
#                    benefits.append(clone_benefit)
#                clone_option['benefits'] = {'add': [benefits]}
                options.append(clone_option)
            res['options'] = {'add': options}
        return res


class GroupProductItemDescriptorRelation(GroupRoot,
        product.ProductItemDescriptorRelation):
    'Relation between Product and Item Descriptor'

    __name__ = 'ins_collective.product-item_desc'


class GroupInsuranceCoverage(GroupRoot, coverage.Coverage):
    'Group Insurance Coverage'

    __name__ = 'ins_collective.coverage'

    product = fields.Many2One('ins_collective.product', 'Product',
        ondelete='CASCADE')


class GroupPackageCoverage(GroupRoot, coverage.PackageCoverage):
    'Link Package Coverage'

    __name__ = 'ins_collective.package-coverage'


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


class GroupSchemaElement(GroupRoot, complementary_data.CoopSchemaElement):
    'Complementary Data Definition'

    __name__ = 'ins_collective.schema_element'


class GroupSchemaElementRelation(GroupRoot,
        complementary_data.SchemaElementRelation):
    'Relation between schema element and complementary data manager'

    __name__ = 'ins_collective.schema_element_relation'


class GroupDynamicDataManager(GroupRoot, complementary_data.DynamicDataManager):
    'Complementary Data Manager'

    __name__ = 'ins_collective.complementary_data_manager'


class GroupPricingComponent(GroupRoot, pricing_rule.PricingComponent):
    'Pricing Data'

    __name__ = 'ins_collective.pricing_component'


class GroupPricingRule(GroupRoot, pricing_rule.PricingRule):
    'Pricing Rule'

    __name__ = 'ins_collective.pricing_rule'

    @classmethod
    def __setup__(cls):
        super(GroupPricingRule, cls).__setup__()
        #In pricing config kind means simple ou multiple prices, in collective
        #you always have at least a price per covered item
        cls.config_kind = copy.copy(cls.config_kind)
        if not cls.config_kind.states:
            cls.config_kind.states = {}
        cls.config_kind.states['invisible'] = True

    @staticmethod
    def default_config_kind():
        return 'advanced'
