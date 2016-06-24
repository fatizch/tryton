from dateutil.relativedelta import relativedelta

from trytond import backend
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields
from trytond.modules.rule_engine import get_rule_mixin
from trytond.modules.currency_cog import ModelCurrency

__metaclass__ = PoolMeta
__all__ = [
    'Benefit',
    'BenefitRule',
    ]

INDEMNIFICATION_KIND = [
    ('capital', 'Capital'),
    ('period', 'Period'),
    ('annuity', 'Annuity'),
    ]
INDEMNIFICATION_DETAIL_KIND = [
    ('waiting_period', 'Waiting Period'),
    ('deductible', 'Deductible'),
    ('benefit', 'Indemnified'),
    ('limit', 'Limit'),
    ('regularization', 'Regularization'),
    ]


class Benefit:
    __name__ = 'benefit'

    indemnification_kind = fields.Selection(INDEMNIFICATION_KIND,
        'Indemnification Kind', sort=False, required=True)
    indemnification_kind_string = indemnification_kind.translated(
        'indemnification_kind')
    benefit_rules = fields.One2Many('benefit.rule', 'benefit', 'Benefit Rules',
        delete_missing=True)
    account_product = fields.Many2One('product.product', 'Account Product',
        ondelete='RESTRICT', required=True)
    automatic_period_calculation = fields.Boolean(
        'Automatic Period Calculation',
        help='Periods will be automatically calculated reusing data from'
        'previous period.',
        states={'invisible': Eval('indemnification_kind') != 'period'},
        depends=['indemnification_kind'])

    def has_automatic_period_calculation(self):
        return self.automatic_period_calculation and \
            self.indemnification_kind == 'period'

    def calculate_benefit(self, args):
        if not self.benefit_rules:
            return
        return self.benefit_rules[0].calculate(args)

    @staticmethod
    def default_indemnification_kind():
        return 'capital'


class BenefitRule(
        get_rule_mixin('indemnification_rule', 'Indemnification Rule'),
        get_rule_mixin('deductible_rule', 'Deductible Rule'),
        model.CoopSQL, model.CoopView, ModelCurrency):
    'Benefit Rule'

    __name__ = 'benefit.rule'

    benefit = fields.Many2One('benefit', 'Benefit', ondelete='CASCADE',
        required=True, select=True)

    @classmethod
    def __setup__(cls):
        super(BenefitRule, cls).__setup__()
        cls.indemnification_rule.domain = [('type_', '=', 'benefit')]
        cls.deductible_rule.domain = [('type_', '=', 'benefit')]

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')
        handler = TableHandler(cls, module)
        # Migrate from 1.6 : rename 'rule' to 'indemnification_rule'
        if handler.column_exist('rule'):
            handler.column_rename('rule', 'indemnification_rule')
            handler.column_rename('rule_extra_data',
                'indemnification_rule_extra_data')
        super(BenefitRule, cls).__register__(module)

    def get_coverage_amount(self, args):
        if 'option' in args and 'covered_person' in args:
            return args['option'].get_coverage_amount(args['covered_person'])

    def calculate(self, args):
        res = []
        loss = args['loss']
        indemnification = args['indemnification']
        delivered = args['service']
        deductible_end_date = self.calculate_deductible_rule(args)
        previous_date = None
        if deductible_end_date:
            # create deductible if deductible rule is defined
            if args['start_date'] <= deductible_end_date:
                end_period = min(args['end_date'], deductible_end_date)
                res.append({
                    'kind': 'deductible',
                    'start_date': args['start_date'],
                    'end_date': end_period,
                    'nb_of_unit': (end_period - args['start_date']).days + 1,
                    'unit': 'day',
                    'amount': 0,
                    'amount_per_unit': 0
                    })
                if args['end_date'] <= deductible_end_date:
                    return res
                else:
                    previous_date = deductible_end_date + relativedelta(days=1)
        if not previous_date:
            previous_date = indemnification.start_date
        dates = [extra_data.date or loss.start_date
            for extra_data in delivered.extra_datas
            if (indemnification.start_date <
                (extra_data.date or loss.start_date) <
                indemnification.end_date)]
        for date in dates:
            new_args = args.copy()
            new_args['date'] = previous_date
            new_args['start_date'] = previous_date
            new_args['end_date'] = date - relativedelta(days=1)
            benefits = self.calculate_indemnification_rule(new_args)
            for benefit in benefits:
                benefit['kind'] = 'benefit'
            res.extend(benefits)
        new_args = args.copy()
        new_args['date'] = previous_date
        new_args['start_date'] = previous_date
        new_args['end_date'] = indemnification.end_date
        benefits = self.calculate_indemnification_rule(new_args) or []
        for benefit in benefits:
            benefit['kind'] = 'benefit'
        res.extend(benefits)
        return res
