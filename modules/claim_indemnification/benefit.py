# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta

from trytond import backend
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import model, fields, coog_date
from trytond.modules.rule_engine import get_rule_mixin
from trytond.modules.currency_cog import ModelCurrency

__metaclass__ = PoolMeta
__all__ = [
    'Benefit',
    'BenefitProduct',
    'BenefitRule',
    ]

INDEMNIFICATION_KIND = [
    ('capital', 'Capital'),
    ('period', 'Period'),
    ('annuity', 'Annuity'),
    ]
INDEMNIFICATION_DETAIL_KIND = [
    ('deductible', 'Deductible'),
    ('benefit', 'Indemnified'),
    ]
ANNUITY_FREQUENCIES = [
    ('', ''),
    ('yearly', 'Yearly'),
    ('half_yearly', 'Half-yearly'),
    ('quarterly', 'Quarterly'),
    ('monthly', 'Monthly'),
    ]


class Benefit:
    __name__ = 'benefit'

    indemnification_kind = fields.Selection(INDEMNIFICATION_KIND,
        'Indemnification Kind', sort=False, required=True)
    indemnification_kind_string = indemnification_kind.translated(
        'indemnification_kind')
    benefit_rules = fields.One2Many('benefit.rule', 'benefit', 'Benefit Rules',
        delete_missing=True)
    automatic_period_calculation = fields.Boolean(
        'Automatic Period Calculation',
        help='Periods will be automatically calculated reusing data from'
        'previous period.',
        states={'invisible': Eval('indemnification_kind') != 'period'},
        depends=['indemnification_kind'])
    products = fields.Many2Many('benefit-product', 'benefit', 'product',
        'Products')

    def has_automatic_period_calculation(self):
        return self.automatic_period_calculation and \
            self.indemnification_kind == 'period'

    def calculate_benefit(self, args):
        if not self.benefit_rules:
            return
        return self.benefit_rules[0].calculate(args)

    def calculate_deductible(self, args):
        if not self.benefit_rules:
            return
        return self.benefit_rules[0].do_calculate_deductible_rule(args)

    @staticmethod
    def default_indemnification_kind():
        return 'capital'


class BenefitProduct(model.CoogSQL):
    'Benefit Product relation'

    __name__ = 'benefit-product'

    benefit = fields.Many2One('benefit', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    product = fields.Many2One('product.product', 'Product', required=True,
        ondelete='RESTRICT')


class BenefitRule(
        get_rule_mixin('indemnification_rule', 'Indemnification Rule'),
        get_rule_mixin('deductible_rule', 'Deductible Rule'),
        get_rule_mixin('revaluation_rule', 'Revaluation Rule'),
        model.CoogSQL, model.CoogView, ModelCurrency):
    'Benefit Rule'

    __name__ = 'benefit.rule'

    benefit = fields.Many2One('benefit', 'Benefit', ondelete='CASCADE',
        required=True, select=True)
    annuity_frequency = fields.Selection(ANNUITY_FREQUENCIES,
        'Annuity Frequency',
            states={
                'invisible': ~Eval('requires_frequency'),
                'required': Bool(Eval('requires_frequency', False))
                },
        depends=['requires_frequency', 'benefit'])
    requires_frequency = fields.Function(
        fields.Boolean('Frequency Required', depends=['benefit']),
        'get_requires_frequency')

    @classmethod
    def __setup__(cls):
        super(BenefitRule, cls).__setup__()
        cls.indemnification_rule.domain = [('type_', '=', 'benefit')]
        cls.deductible_rule.domain = [('type_', '=', 'benefit_deductible')]
        cls.revaluation_rule.domain = [('type_', '=', 'revaluation_rule')]

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

    @fields.depends('benefit', 'requires_frequency')
    def on_change_benefit(self):
        if self.benefit is None:
            self.requires_frequency = False
        else:
            self.requires_frequency = (self.benefit.indemnification_kind ==
                'annuity')

    def get_requires_frequency(self, name):
        if not self.benefit:
            return False
        return self.benefit.indemnification_kind == 'annuity'

    def get_coverage_amount(self, args):
        if 'option' in args and 'covered_person' in args:
            return args['option'].get_coverage_amount(args['covered_person'])

    @classmethod
    def calculation_dates(cls, indemnification, start_date, end_date):
        res = set()
        for service in indemnification.service.loss.services:
            if service == indemnification.service:
                continue
            for indemn in service.indemnifications:
                for detail in indemn.details:
                    if (detail.start_date > start_date and
                            detail.start_date < end_date):
                        res.add(detail.start_date)
        return res

    @classmethod
    def clean_benefits(cls, benefits):
        benefits = sorted(benefits, key=lambda x: x['start_date'])
        cleaned = []
        for period in benefits:
            if (not cleaned or period['amount_per_unit'] !=
                    cleaned[-1]['amount_per_unit'] or
                    period['unit'] != cleaned[-1]['unit']
                    and (cleaned[-1]['end_date'] -
                        period['start_date']).days == 1):
                cleaned.append(period)
            else:
                cleaned[-1]['end_date'] = period['end_date']
                cleaned[-1]['nb_of_unit'] = period['nb_of_unit'] + \
                    cleaned[-1]['nb_of_unit']
                cleaned[-1]['amount'] = (cleaned[-1]['nb_of_unit'] *
                    cleaned[-1]['amount_per_unit'])
        return cleaned

    def calculate(self, args):
        res = []
        loss = args['loss']
        indemnification = args['indemnification']
        delivered = args['service']
        deductible_end_date = self.do_calculate_deductible_rule(args)
        previous_date = None
        args['limit_date'] = None
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
                    'base_amount': 0,
                    'amount_per_unit': 0
                    })
                if args['end_date'] <= deductible_end_date:
                    return res
                else:
                    previous_date = deductible_end_date + relativedelta(days=1)
        if not previous_date:
            previous_date = indemnification.start_date
        dates = {extra_data.date or loss.start_date
            for extra_data in delivered.extra_datas
            if (indemnification.start_date <
                (extra_data.date or loss.start_date) <
                indemnification.end_date)}
        # Add pivot periods
        dates |= self.calculation_dates(indemnification, previous_date,
            args['end_date'])
        all_benefits = []

        must_revaluate = self.must_revaluate()
        for start_date, end_date in coog_date.calculate_periods_from_dates(
                list(dates), previous_date, args['end_date']):
            new_args = args.copy()
            new_args['date'] = start_date
            new_args['indemnification_detail_start_date'] = start_date
            new_args['indemnification_detail_end_date'] = end_date
            benefits = self.do_calculate_indemnification_rule(new_args)
            if must_revaluate:
                for benefit in benefits:
                    reval_args = new_args.copy()
                    reval_args['indemnification_detail_start_date'] = \
                        benefit['start_date']
                    reval_args['indemnification_detail_end_date'] = \
                        benefit['end_date']
                    reval_args.update(benefit)
                    reval_benefits = self.do_calculate_revaluation_rule(
                        reval_args) or []
                    for reval_benefit in reval_benefits:
                        tmp_benefit = benefit.copy()
                        tmp_benefit.update(reval_benefit)
                        all_benefits.append(tmp_benefit)
            else:
                all_benefits.extend(benefits)
        for benefit in all_benefits:
            benefit['kind'] = 'benefit'
        all_benefits = self.clean_benefits(all_benefits)
        res.extend(all_benefits)
        return res

    def do_calculate_indemnification_rule(self, args):
        return self.calculate_indemnification_rule(args)

    def do_calculate_deductible_rule(self, args):
        return self.calculate_deductible_rule(args)

    def do_calculate_revaluation_rule(self, args):
        return self.calculate_revaluation_rule(args)

    def must_revaluate(self):
        return self.revaluation_rule is not None
