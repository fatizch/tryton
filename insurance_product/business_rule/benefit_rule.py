#-*- coding:utf-8 -*-
from trytond.model import fields
from trytond.pyson import Eval, Or

from trytond.modules.coop_utils import model, coop_string, date
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_SIMPLE
from trytond.modules.insurance_product.product import DEF_CUR_DIG
from trytond.modules.insurance_product.benefit import INDEMNIFICATION_KIND


__all__ = [
    'BenefitRule',
    ]

AMOUNT_KIND = [
    ('amount', 'Amount'),
    ('cov_amount', 'Coverage Amount'),
]


class BenefitRule(BusinessRuleRoot, model.CoopSQL):
    'Benefit Rule'

    __name__ = 'ins_product.benefit_rule'

    amount_kind = fields.Selection(AMOUNT_KIND, 'Amount Kind',
        states={'invisible': STATE_SIMPLE}, )
    amount = fields.Numeric('Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={
            'invisible':
                Or(
                    STATE_SIMPLE,
                    Eval('amount_kind') != 'amount',
                )
        })
    coef_coverage_amount = fields.Numeric('Multiplier',
        states={
            'invisible':
                Or(
                    STATE_SIMPLE,
                    Eval('amount_kind') != 'cov_amount',
                )
        }, help='Add a multiplier to apply to the coverage amount', )
    indemnification_calc_unit = fields.Selection(date.DAILY_DURATION,
        'Indemnification Calculation Unit',
        states={
            'invisible': Eval('_parent_offered', {}).get(
                'indemnification_kind') != 'period',
        }, sort=False)

    @staticmethod
    def default_coef_coverage_amount():
        return 1

    @staticmethod
    def default_amount_kind():
        return 'cov_amount'

    def get_simple_rec_name(self):
        if self.amount_kind == 'amount':
            return self.amount
        else:
            res = coop_string.translate_value(self, 'amount_kind')
            if self.coef_coverage_amount != 1:
                res = '%s * %s' % (self.coef_coverage_amount, res)
            return res

    @staticmethod
    def default_indemnification_calc_unit():
        return 'day'

    def get_simple_result(self, args):
        if self.amount_kind == 'amount':
            return self.amount
        else:
            #TODO: retrive coverage amount
            raise NotImplementedError

    def get_indemnification_for_period(self, args):
        errs = []
        res = {}
        if not 'start_date' in args:
            errs += 'missing_date'
        else:
            res['start_date'] = args['start_date']
        if not 'end_date' in args:
            nb = 1
        else:
            nb = date.duration_between(args['start_date'], args['end_date'],
            self.indemnification_calc_unit)
            res['end_date'] = args['end_date']
        res['nb_of_unit'] = nb
        res['unit'] = self.indemnification_calc_unit
        res['amount_per_unit'], re_errs = self.give_me_result(args)
        return res, errs + re_errs

    def get_indemnification_for_capital(self, args):
        res = {}
        res['nb_of_unit'] = 1
        res['amount_per_unit'], errs = self.give_me_result(args)
        return res, errs

    def give_me_benefit(self, args):
        if self.offered.indemnification_kind == 'period':
            return self.get_indemnification_for_period(args)
        else:
            return self.get_indemnification_for_capital(args)
