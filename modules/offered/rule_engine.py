# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, model
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'RuleEngine',
    'OptionDescriptionEndingRule',
    ]


class RuleEngineResultLine(object):
    '''
        This class is the root of all rule engine result classes
    '''

    def __init__(self, rule_errors=None):
        super(RuleEngineResultLine, self).__init__()
        self.rule_errors = rule_errors or []


class PricingResultDetail(object):
    def __init__(self, amount=0, on_object=None, details=None,
            to_recalculate=False, kind=''):
        self.amount = amount
        self.on_object = on_object
        self.details = details or []
        self.to_recalculate = to_recalculate
        self.kind = kind


class PricingResultLine(RuleEngineResultLine):
    def __init__(self, amount=0, contract=None, start_date=None, end_date=None,
            on_object=None, frequency=None, details=None):
        self.amount = amount
        self.contract = contract
        self.start_date = start_date
        self.end_date = end_date
        self.on_object = on_object
        self.frequency = frequency
        self.details = details or []

    def __repr__(self):
        return str(self)

    def __str__(self):
        return '%s EUR %s %s %s' % (self.amount, self.contract,
            self.start_date, self.on_object)

    def init_from_args(self, args):
        if 'contract' in args:
            self.contract = args['contract']
        if 'date' in args:
            self.start_date = args['date']

    def add_detail(self, detail):
        self.amount += detail.amount
        self.details.append(detail)

    def add_detail_from_line(self, other_line):
        if not self.frequency and other_line.frequency:
            self.frequency = other_line.frequency
        elif (other_line.frequency and
                not self.frequency == other_line.frequency):
            # TODO : remove this once the frequency consistency checking is
            # performed on the managers
            raise Exception('Frequencies do not match')
        self.amount += other_line.amount
        new_detail = PricingResultDetail(other_line.amount,
            other_line.on_object, details=other_line.details)
        self.details.append(new_detail)


class RuleEngine:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.append(('ending', 'Ending'))

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'ending':
            return 'date'
        return super(RuleEngine, self).on_change_with_result_type(name)


class OptionDescriptionEndingRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
    'Option Description Ending Rule'

    __name__ = 'offered.option.description.ending_rule'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    coverage = fields.Many2One('offered.option.description', 'Coverage',
        required=True, ondelete='CASCADE', select=True)

    @classmethod
    def __setup__(cls):
        super(OptionDescriptionEndingRule, cls).__setup__()
        cls.rule.required = True
        cls.rule.domain = [('type_', '=', 'ending')]

    @classmethod
    def _export_light(cls):
        return super(OptionDescriptionEndingRule, cls)._export_light() | {
            'rule'}

    def get_func_key(self, name):
        return self.coverage.code

    @classmethod
    def search_func_key(cls, name, clause):
        return [('coverage.code',) + tuple(clause[1:])]
