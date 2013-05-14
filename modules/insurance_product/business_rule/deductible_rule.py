#-*- coding:utf-8 -*-
from trytond.pyson import Eval, Or, And

from trytond.modules.coop_utils import model, date, fields, coop_string
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_ADVANCED


__all__ = [
    'DeductibleRule',
    'DeductibleDuration',
]


DEDUCTIBLE_KIND = [
    ('amount', 'Amount'),
    ('duration', 'Duration'),
]


class DeductibleRule(BusinessRuleRoot, model.CoopSQL):
    'Deductible Rule'

    __name__ = 'ins_product.deductible_rule'

    kind = fields.Selection(DEDUCTIBLE_KIND, 'Kind', sort=False, required=True)
    simple_config_choice = fields.Selection(
        [('value', 'Value'), ('list', 'List')], 'Simple Config. Choice',
        sort=False, states={
            'invisible': Or(STATE_ADVANCED, Eval('kind') != 'duration'),
            'required': And(~STATE_ADVANCED, Eval('kind') == 'duration'),
            }
        )
    amount = fields.Numeric('Amount', states={
            'invisible': Or(STATE_ADVANCED, Eval('kind') != 'amount'),
            'required': And(~STATE_ADVANCED, Eval('kind') == 'amount'),
            })
    duration = fields.Integer('Duration', states={
            'invisible': Or(STATE_ADVANCED, Eval('kind') != 'duration',
                Eval('simple_config_choice') != 'value'),
            'required': And(~STATE_ADVANCED, Eval('kind') == 'duration',
                Eval('simple_config_choice') == 'value'),
            })
    duration_unit = fields.Selection(date.DAILY_DURATION, 'Duration Unit',
        states={
            'invisible': Or(STATE_ADVANCED, Eval('kind') != 'duration',
                Eval('simple_config_choice') != 'value'),
            'required': And(~STATE_ADVANCED, Eval('kind') == 'duration',
                Eval('simple_config_choice') == 'value'),
            })
    durations = fields.One2Many('ins_product.deductible_duration',
        'deductible_rule', 'Durations', states={
            'invisible': Or(STATE_ADVANCED, Eval('kind') != 'duration',
                Eval('simple_config_choice') != 'list'),
            'required': And(~STATE_ADVANCED, Eval('kind') == 'duration',
                Eval('simple_config_choice') == 'list'),
            })
    scope = fields.Selection(
        [('coverage', 'Coverage'), ('covered', 'Covered Element')], 'Scope',
        states={
            'invisible': Or(STATE_ADVANCED, Eval('kind') != 'duration',
                Eval('simple_config_choice') != 'list'),
            'required': And(~STATE_ADVANCED, Eval('kind') == 'duration',
                Eval('simple_config_choice') == 'list'),
            })

    def get_simple_rec_name(self):
        if self.simple_config_choice == 'value':
            res = self.get_simple_result()[0]
            if not res:
                return ''
            if self.kind == 'duration' and len(res) > 1:
                return '%s %s' % (res[0], res[1])
            else:
                return str(res)
        else:
            if self.kind == 'duration' and self.durations:
                return ', '.join([x.get_rec_name('') for x in self.durations])

    def get_simple_result(self, args=None):
        if self.kind == 'amount':
            return self.amount, []
        elif self.kind == 'duration':
            return (self.duration, self.duration_unit), []
        else:
            return None, []

    def give_me_result(self, args):
        #The deductible could be set at a higher level, the coverage,
        #or a choice could be stored on the covered data or the option
        if args['deductible_duration']:
            return args['deductible_duration'].get_value(), []
        return super(DeductibleRule, self).give_me_result(args)

    def get_deductible_duration(self, args):
        errs = []
        res = {}
        if self.kind != 'duration':
            return None, errs
        if not 'start_date' in args:
            errs += 'missing_date'
            return None, errs
        res['start_date'] = args['start_date']
        (duration, unit), cur_errs = self.give_me_result(args)
        errs += cur_errs
        if not duration or not unit:
            errs = 'missing_duration_or_duration_unit'
            return None, errs
        end_date = date.get_end_of_period(args['start_date'], duration, unit)
        if 'end_date' in args and args['end_date']:
            end_date = min(end_date, args['end_date'])
        res['end_date'] = end_date
        res['nb_of_unit'] = date.duration_between(res['start_date'],
            res['end_date'], 'day')
        res['unit'] = unit
        res['amount_per_unit'] = 0
        return [res], errs

    def get_deductible_amount(self, args):
        res = {}
        res['amount_per_unit'], errs = self.give_me_result(args)
        res['nb_of_unit'] = -1
        return [res], errs

    def give_me_deductible(self, args):
        if self.kind == 'duration':
            return self.get_deductible_duration(args)
        else:
            return self.get_deductible_amount(args)

    @staticmethod
    def default_simple_config_choice():
        return 'value'

    @staticmethod
    def default_scope():
        return 'covered'

    def give_me_possible_deductible_duration(self, args):
        if not (self.kind == 'duration' and self.config_kind == 'simple'
                and self.simple_config_choice == 'list'
                and args['scope'] == self.scope):
            return []
        else:
            return list(self.durations)


class DeductibleDuration(model.CoopSQL, model.CoopView):
    'Deductible Duration'

    __name__ = 'ins_product.deductible_duration'

    deductible_rule = fields.Many2One('ins_product.deductible_rule',
        'Deductible Rule')
    duration = fields.Integer('Duration', required=True)
    duration_unit = fields.Selection(date.DAILY_DURATION, 'Duration Unit',
        required=True)

    def get_rec_name(self, name):
        return '%s %s' % (self.duration,
            coop_string.translate_value(self, 'duration_unit'))

    def get_value(self):
        return self.duration, self.duration_unit
