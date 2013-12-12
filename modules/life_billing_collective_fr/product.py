from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import fields, model, utils, coop_string
from trytond.modules.rule_engine import RuleEngineResult
from trytond.modules.insurance_product import business_rule

__all__ = [
    'Product',
    'Coverage',
    'CollectiveRatingRule',
    'SubRatingRule',
    'FareClass',
    'FareClassGroup',
    'FareClassGroupFareClassRelation',
    ]

__metaclass__ = PoolMeta


class Product():
    'Product'

    __name__ = 'offered.product'

    use_rates = fields.Function(
        fields.Boolean('Use Rates', states={'invisible': True}),
        'get_use_rates')

    def get_collective_rating_frequency(self):
        return 'quarterly'

    def get_use_rates(self, name):
        return self.is_group and any([x.rating_rules for x in self.coverages])


class Coverage():
    'Coverage'

    __name__ = 'offered.option.description'

    is_rating_by_fare_class = fields.Function(
        fields.Boolean('Rating by Fare Class', states={'invisible': True}),
        'get_rating_by_fare_class')
    use_rates = fields.Function(
        fields.Boolean('Use Rates', states={'invisible': True}),
        'get_use_rates')
    rating_rules = fields.One2Many('billing.premium.rate.rule', 'offered',
        'Rating Rules', states={'invisible': ~Eval('is_group')})

    def get_rating_by_fare_class(self, name):
        if utils.is_none(self, 'rating_rules'):
            return False
        for rating_rule in self.rating_rules:
            if rating_rule.rating_kind == 'fare_class':
                return True
        return False

    def get_use_rates(self, name):
        return self.is_group and len(self.rating_rules) > 0


class FareClass(model.CoopSQL, model.CoopView):
    'Fare Class'

    __name__ = 'fare_class'

    code = fields.Char('Code', on_change_with=['code', 'name'], required=True)
    name = fields.Char('Name')

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


class FareClassGroup(model.CoopSQL, model.CoopView):
    'Fare Class Group'

    __name__ = 'fare_class.group'

    code = fields.Char('Code', on_change_with=['code', 'name'], required=True)
    name = fields.Char('Name')
    fare_classes = fields.Many2Many('fare_class.group-fare_class',
        'group', 'fare_class', 'Fare Classes')

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


class FareClassGroupFareClassRelation(model.CoopSQL):
    'Relation between fare class group and fare class'

    __name__ = 'fare_class.group-fare_class'

    group = fields.Many2One('fare_class.group', 'Group',
        ondelete='CASCADE')
    fare_class = fields.Many2One('fare_class', 'Fare Class',
        ondelete='RESTRICT')


class CollectiveRatingRule(business_rule.BusinessRuleRoot, model.CoopSQL):
    'Collective Rating Rule'

    __name__ = 'billing.premium.rate.rule'

    rating_kind = fields.Selection(
        [('tranche', 'by Tranche'), ('fare_class', 'by Fare Class')],
        'Rating Kind', states={'readonly': ~~Eval('sub_rating_rules')})
    sub_rating_rules = fields.One2Many('billing.premium.rate.rule.line',
        'main_rating_rule', 'Sub Rating Rules')
    index = fields.Many2One('table.table_def', 'Index',
        domain=[
            ('dimension_kind1', '=', 'range-date'),
            ('dimension_kind2', '=', None),
            ], states={'invisible': Eval('rating_kind') != 'fare_class'},
            ondelete='RESTRICT')

    def give_me_rate(self, args):
        result = []
        errs = []
        for cov_data in args['option'].covered_data:
            #TODO deal with date control, do not rate a future covered data
            cov_data_dict = {'covered_data': cov_data, 'rates': [],
                'date': args['date']}
            result.append(cov_data_dict)
            cov_data_args = args.copy()
            cov_data.init_dict_for_rule_engine(cov_data_args)
            for sub_rule in self.sub_rating_rules:
                if self.rating_kind == 'fare_class':
                    if sub_rule.fare_class_group != cov_data.fare_class_group:
                        continue
                    cov_data_args['fare_class'] = sub_rule.fare_class
                    cov_data_args['fare_class_group'] = \
                        cov_data.fare_class_group
                rule_engine_res = sub_rule.get_result(cov_data_args)
                if rule_engine_res.errors:
                    errs += rule_engine_res.errors
                    continue
                cur_dict = {'rate': rule_engine_res.result}
                if self.rating_kind == 'fare_class':
                    cur_dict['key'] = sub_rule.fare_class
                    cur_dict['index'] = self.index
                    cur_dict['kind'] = 'fare_class'
                elif self.rating_kind == 'tranche':
                    cur_dict['key'] = sub_rule.tranche
                    cur_dict['kind'] = 'tranche'
                cov_data_dict['rates'].append(cur_dict)
        return result, errs

    @staticmethod
    def default_rating_kind():
        return 'fare_class'


class SubRatingRule(model.CoopView, model.CoopSQL):
    'Sub Rating Rule'

    __name__ = 'billing.premium.rate.rule.line'

    main_rating_rule = fields.Many2One('billing.premium.rate.rule',
        'Main Rating Rule', ondelete='CASCADE')
    tranche = fields.Many2One('salary_range', 'Tranche',
        states={'invisible': Eval('_parent_main_rating_rule', {}).get(
                'rating_kind', '') != 'tranche'}, ondelete='RESTRICT')
    fare_class_group = fields.Many2One('fare_class.group',
        'Fare Class Group',
        states={'invisible': Eval('_parent_main_rating_rule', {}).get(
                    'rating_kind', '') != 'fare_class'}, ondelete='RESTRICT',
        domain=[('fare_classes', '=', Eval('fare_class'))],
        depends=['fare_class'])
    fare_class = fields.Many2One('fare_class', 'Fare Class',
        states={'invisible': Eval('_parent_main_rating_rule', {}).get(
                    'rating_kind', '') != 'fare_class'},
        ondelete='RESTRICT')
    config_kind = fields.Selection(business_rule.CONFIG_KIND, 'Conf. kind',
        required=True)
    simple_rate = fields.Numeric('Rate',
        states={'invisible': ~business_rule.STATE_SIMPLE}, digits=(16, 4))
    rule = fields.Many2One('rule_engine', 'Rule', ondelete='RESTRICT',
        states={'invisible': ~business_rule.STATE_ADVANCED})

    @staticmethod
    def default_config_kind():
        return 'simple'

    def get_result(self, args):
        if self.config_kind == 'simple':
            return RuleEngineResult(self.simple_rate)
        elif self.rule:
            return self.rule.execute(args)
