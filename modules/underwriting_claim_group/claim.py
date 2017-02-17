# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Or, And

from trytond.modules.coog_core import model, fields

__all__ = [
    'Benefit',
    'BenefitUnderwritingRule',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    underwriting_rules = fields.Many2Many('benefit-underwriting_rule',
        'benefit', 'rule', 'Underwriting Rules', states={
            'invisible': Eval('force_underwriting_rule', False)},
        depends=['force_underwriting_rule'])
    force_underwriting_rule = fields.Function(
        fields.Boolean('Force Underwriting Rule',
            states={'invisible': ~Eval('is_group')},
            depends=['is_group']),
        'get_force_rule', setter='setter_void')

    @classmethod
    def __setup__(cls):
        super(Benefit, cls).__setup__()
        cls.underwriting_rule.states['invisible'] = And(
            cls.underwriting_rule.states.get('invisible', True),
            ~Eval('force_underwriting_rule'))
        cls.underwriting_rule.depends.append('force_underwriting_rule')
        cls.underwriting_rule_extra_data.states['invisible'] = Or(
            cls.underwriting_rule_extra_data.states.get('invisible', True),
            ~Eval('force_underwriting_rule'))
        cls.underwriting_rule_extra_data.depends.append(
            'force_underwriting_rule')

    @classmethod
    def default_force_underwriting_rule(cls):
        return True

    @fields.depends('force_underwriting_rule', 'underwriting_rule',
        'underwriting_rule_extra_data', 'underwriting_rules')
    def on_change_force_underwriting_rule(self):
        if self.force_underwriting_rule:
            self.underwriting_rule = None
            self.underwriting_rule_extra_data = {}
            self.underwriting_rules = []
        else:
            self.underwriting_rules = [self.underwriting_rule] \
                if self.underwriting_rule else []
            self.underwriting_rule = None
            self.underwriting_rule_extra_data = {}

    def calculate_underwriting_rule(self, args):
        option = args.get('option', None)
        if not option or self.force_underwriting_rule:
            return super(Benefit, self).calculate_underwriting_rule(args)
        version = option.get_version_at_date(args['date'])
        option_benefit = version.get_benefit(self)
        if not option_benefit.underwriting_rule:
            return None, None
        return option_benefit.calculate_underwriting_rule(args)

    def get_force_rule(self, name):
        return bool(getattr(self, name[6:]))


class BenefitUnderwritingRule(model.CoogSQL):
    'Benefit - Underwriting Rule'

    __name__ = 'benefit-underwriting_rule'

    benefit = fields.Many2One('benefit', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='RESTRICT')
