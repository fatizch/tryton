from trytond.pool import PoolMeta
from trytond.pyson import Eval, Or

from trytond.modules.coop_utils import fields, model, utils
from trytond.modules.rule_engine import RuleEngineResult
from trytond.modules.insurance_product import business_rule

__all__ = [
    'Coverage',
    'CollectiveRatingRule',
    'TrancheRatingRule',
    ]

__metaclass__ = PoolMeta


class Coverage():
    'Coverage'

    __name__ = 'offered.coverage'

    rating_rules = fields.One2Many('collective.rating_rule', 'offered',
        'Rating Rules', states={'invisible': ~Eval('is_group')})


class CollectiveRatingRule(business_rule.BusinessRuleRoot, model.CoopSQL):
    'Collective Rating Rule'

    __name__ = 'collective.rating_rule'

    rating_kind = fields.Selection(
        [('tranche', 'by Tranche'), ('index', 'by Index')], 'Rating Kind')
    rates_by_tranche = fields.One2Many('collective.rating_rule_by_tranche',
        'main_rating_rule', 'Rate by Tranche',
        states={'invisible': Eval('rating_kind') != 'tranche'})
    simple_rate = fields.Numeric('Rate',
            states={'invisible': Or(
                    ~business_rule.STATE_SIMPLE,
                    Eval('rating_kind') != 'index'
                    )}, digits=(16, 4))
    index = fields.Many2One('table.table_def', 'Index',
        domain=[
            ('dimension_kind1', '=', 'range-date'),
            ('dimension_kind2', '=', None),
            ], states={'invisible': Eval('rating_kind') != 'index'},
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(CollectiveRatingRule, cls).__setup__()
        utils.update_states(cls, 'config_kind',
            {'invisible': Eval('rating_kind') == 'tranche'})

    def get_simple_result(self, args):
        return self.simple_rate

    def give_me_rate(self, args):
        result = []
        errs = []
        for covered_data in args['option'].covered_data:
            #TODO deal with date control, do not rate a future covered data
            covered_data_dict = {'covered_data': covered_data, 'rates': []}
            result.append(covered_data_dict)
            covered_data_args = args.copy()
            covered_data.init_dict_for_rule_engine(covered_data_args)
            if self.rating_kind == 'index':
                rule_engine_res = self.give_me_result(covered_data_args)
                if rule_engine_res.errors:
                    errs += rule_engine_res.errors
                else:
                    covered_data_dict['rates'].append({
                            'key': self.index,
                            'rate': rule_engine_res.result,
                            'kind': 'index',
                            })
            elif self.rating_kind == 'tranche':
                for tranche_rate in self.rates_by_tranche:
                    rule_engine_res = tranche_rate.get_result(
                        covered_data_args)
                    if rule_engine_res.errors:
                        errs += rule_engine_res.errors
                    else:
                        covered_data_dict['rates'].append({
                                'key': tranche_rate.tranche,
                                'rate': rule_engine_res.result,
                                'kind': 'tranche',
                                })
        return result, errs

    @staticmethod
    def default_rating_kind():
        return 'index'


class TrancheRatingRule(model.CoopView, model.CoopSQL):
    'Tranche Rating Rule'

    __name__ = 'collective.rating_rule_by_tranche'

    main_rating_rule = fields.Many2One('collective.rating_rule',
        'Main Rating Rule', ondelete='CASCADE')
    tranche = fields.Many2One('tranche.tranche', 'Tranche',
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
            return utils.execute_rule(self, self.rule, args)
