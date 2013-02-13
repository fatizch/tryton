#-*- coding:utf-8 -*-
from trytond.model import fields
from trytond.pyson import Eval, Or

from trytond.modules.coop_utils import model, date
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_SIMPLE


__all__ = [
    'DeductibleRule',
    ]


DEDUCTIBLE_KIND = [
    ('amount', 'Amount'),
    ('duration', 'Duration'),
]


class DeductibleRule(BusinessRuleRoot, model.CoopSQL):
    'Deductible Rule'

    __name__ = 'ins_product.deductible_rule'

    kind = fields.Selection(DEDUCTIBLE_KIND, 'Kind', sort=False)
    amount = fields.Char('Amount',
        states={'invisible': Or(STATE_SIMPLE, Eval('kind') != 'amount')})
    duration = fields.Integer('Duration',
        states={'invisible': Or(STATE_SIMPLE, Eval('kind') != 'duration')})
    duration_unit = fields.Selection(date.DAILY_DURATION, 'Duration Unit',
        states={'invisible': Or(STATE_SIMPLE, Eval('kind') != 'duration')})

    def get_simple_rec_name(self):
        res = self.get_simple_result()[0]
        if not res:
            return ''
        if len(res) > 1:
            return '%s %s' % (res[0], res[1])
        else:
            return str(res)

    def get_simple_result(self, args=None):
        if self.kind == 'amount':
            return self.amount, []
        elif self.kind == 'duration':
            return (self.duration, self.duration_unit), []
        else:
            return None, []

    def give_me_deductible(self, args):
        errs = []
        res = {}
        if self.kind != 'duration':
            return None, errs
        if not 'start_date' in args:
            errs += 'missing_date'
            return None, errs
        res['start_date'] = args['start_date']
        end_date = date.add_duration(args['start_date'], self.duration,
            self.duration_unit)
        if 'end_date' in args and args['end_date']:
            end_date = min(end_date, args['end_date'])
        res['end_date'] = end_date
        res['nb_of_unit'] = date.duration_between(res['start_date'],
            res['end_date'], 'day')
        res['unit'] = self.duration_unit
        res['amount_per_unit'] = 0
        return res, errs
