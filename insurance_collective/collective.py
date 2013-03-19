#-*- coding:utf-8 -*-
import copy

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.insurance_product import product
from trytond.modules.insurance_product import coverage
from trytond.modules.coop_utils import utils, model
from trytond.modules.insurance_product.business_rule import pricing_rule
from trytond.modules.insurance_product import PricingResultLine

__all__ = [
    'GroupRoot',
    'GroupProduct',
    'GroupProductItemDescriptorRelation',
    'GroupCoverage',
    'GroupProductCoverageRelation',
    'GroupPackageCoverage',
    'GroupPricingRule',
    'GroupProductComplementaryDataRelation',
    'GroupCoverageComplementaryDataRelation',
    'StatusHistory',
]


class GroupRoot(object):

    @classmethod
    def __setup__(cls):
        cls._table = None
        super(GroupRoot, cls).__setup__()

    @classmethod
    def get_offered_module_prefix(cls):
        return 'ins_collective'


class GroupProduct(GroupRoot, product.Product):
    'Group Insurance Plan'

    __name__ = 'ins_collective.product'

    @classmethod
    def __setup__(cls):
        cls.contract_generator = copy.copy(cls.contract_generator)
        cls.contract_generator.required = False
        cls.contract_generator.states['required'] = ~Eval('template')
        cls.contract_generator.depends = ['template']

        cls.template = copy.copy(cls.template)
        cls.template.on_change = ['template', 'options', 'start_date']

        cls.options = copy.copy(cls.options)
        cls.options.relation_name = 'ins_collective.product-coverage'

        cls.item_descriptors = copy.copy(cls.item_descriptors)
        cls.item_descriptors.relation_name = 'ins_collective.product-item_desc'

        cls.complementary_data_def = copy.copy(cls.complementary_data_def)
        cls.complementary_data_def.relation_name = \
            'ins_collective.product-complementary_data_def'

        super(GroupProduct, cls).__setup__()

    def get_subscriber(self):
        subscriber_id = Transaction().context.get('subscriber')
        if not subscriber_id:
            return
        return Pool().get('party.party')(subscriber_id)

    def on_change_template(self):
        res = super(GroupProduct, self).on_change_template()
        if not self.template:
            res['options'] = []
        else:
            subscriber = self.get_subscriber()
            prefix = ''
            if subscriber:
                prefix = subscriber.code
            res['code'] = prefix + self.template.code
            res['name'] = prefix + self.template.name
            options = []
            for option in self.template.options:
                clone_option = utils.create_inst_with_default_val(
                    self.__class__, 'options')[0]
                clone_option['code'] = prefix + option.code
                clone_option['name'] = prefix + option.name
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

    @classmethod
    def get_pricing_rule_model(cls):
        return 'ins_collective.pricing_rule'


class GroupProductItemDescriptorRelation(GroupRoot,
        product.ProductItemDescriptorRelation):
    'Relation between Product and Item Descriptor'

    __name__ = 'ins_collective.product-item_desc'

    @classmethod
    def __setup__(cls):
        cls.product = copy.copy(cls.product)
        cls.product.model_name = 'ins_collective.product'
        super(GroupProductItemDescriptorRelation, cls).__setup__()


class GroupCoverage(GroupRoot, model.CoopSQL, coverage.SimpleCoverage):
    'Group Insurance Coverage'

    __name__ = 'ins_collective.coverage'

    @classmethod
    def get_pricing_rule_model(cls):
        return 'ins_collective.pricing_rule'

    @classmethod
    def __setup__(cls):
        cls.coverages_in_package = copy.copy(cls.coverages_in_package)
        cls.coverages_in_package.relation_name = \
            'ins_collective.package-coverage'
        cls.complementary_data_def = copy.copy(cls.complementary_data_def)
        cls.complementary_data_def.relation_name = \
            'ins_collective.coverage-complementary_data_def'
        super(GroupCoverage, cls).__setup__()


class GroupProductCoverageRelation(GroupRoot, product.ProductOptionsCoverage):
    'Define Product - Coverage relations'

    __name__ = 'ins_collective.product-coverage'

    @classmethod
    def __setup__(cls):
        cls.product = copy.copy(cls.product)
        cls.product.model_name = 'ins_collective.product'
        cls.coverage = copy.copy(cls.coverage)
        cls.coverage.model_name = 'ins_collective.coverage'
        super(GroupProductCoverageRelation, cls).__setup__()


class GroupPackageCoverage(GroupRoot, coverage.PackageCoverage):
    'Link Package Coverage'

    __name__ = 'ins_collective.package-coverage'

    @classmethod
    def __setup__(cls):
        cls.package = copy.copy(cls.package)
        cls.package.model_name = 'ins_collective.coverage'
        cls.coverage = copy.copy(cls.coverage)
        cls.coverage.model_name = 'ins_collective.coverage'
        super(GroupPackageCoverage, cls).__setup__()


class GroupPricingRule(GroupRoot, pricing_rule.SimplePricingRule,
        model.CoopSQL):
    'Pricing Rule'

    __name__ = 'ins_collective.pricing_rule'

    def give_me_price(self, args):
        return PricingResultLine(value=0), []

    def give_me_sub_elem_price(self, args):
        value, errs = self.give_me_result(args)
        result = PricingResultLine(value=value)
        return result, errs


class GroupProductComplementaryDataRelation(GroupRoot,
        product.ProductComplementaryDataRelation):
    'Relation between Product and Complementary Data'

    __name__ = 'ins_collective.product-complementary_data_def'

    @classmethod
    def __setup__(cls):
        cls.product = copy.copy(cls.product)
        cls.product.model_name = 'ins_collective.product'
        super(GroupProductComplementaryDataRelation, cls).__setup__()


class GroupCoverageComplementaryDataRelation(GroupRoot,
        coverage.CoverageComplementaryDataRelation):
    'Relation between Coverage and Complementary Data'

    __name__ = 'ins_collective.coverage-complementary_data_def'

    @classmethod
    def __setup__(cls):
        cls.coverage = copy.copy(cls.coverage)
        cls.coverage.model_name = 'ins_collective.coverage'
        super(GroupCoverageComplementaryDataRelation, cls).__setup__()


class StatusHistory(model.CoopSQL, model.CoopView):
    'Status History'

    __name__ = 'ins_contract.status_history'
    __metaclass__ = PoolMeta

    @classmethod
    def get_possible_reference(cls):
        res = super(StatusHistory, cls).get_possible_reference()
        res.append(('ins_collective.contract', 'Collective Contract')),
        res.append(('ins_collective.option', 'Collective Option')),
        return res
