# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import fields, model
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'OptionDescription',
    'OptionDescriptionSurrenderRule',
    ]


class OptionDescription:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    surrender_rules = fields.One2Many(
        'offered.option.description.surrender_rule', 'coverage',
        'Surrender Rules', delete_missing=True, size=1)


class OptionDescriptionSurrenderRule(model.CoogSQL, model.CoogView,
        get_rule_mixin('rule', 'Rule', extra_string='Rule Extra Data'),
        get_rule_mixin('eligibility_rule', 'Eligibility Rule',
            extra_string='Eligibility Rule Extra Data')):
    'Option Description Surrender Rule'
    __name__ = 'offered.option.description.surrender_rule'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        required=True, ondelete='CASCADE', select=True)
    surrender_account = fields.Many2One('account.account', 'Surrender Account',
        ondelete='RESTRICT', states={
            'invisible': ~Eval('rule', False),
            'required': Bool(Eval('rule', False))},
        depends=['rule'],
        help='The account that will be used to pay surrender lines for this '
        'coverage')

    @classmethod
    def __setup__(cls):
        super(OptionDescriptionSurrenderRule, cls).__setup__()
        cls.rule.domain = [('type_', '=', 'surrender')]
        cls.rule.help = 'If set, the rule result will be used to ' \
            'compute the surrender value of the contract'
        cls.eligibility_rule.domain = [('type_', '=',
                'surrender_eligibility')]
        cls.eligibility_rule.help = 'If set, the rule result must ' \
            'be True to allow surrendering of the contract'
        cls.eligibility_rule.states = {
            'invisible': ~Eval('rule', False),
            }
        cls.eligibility_rule.depends = ['rule']

    @classmethod
    def _export_light(cls):
        return super(OptionDescriptionSurrenderRule, cls)._export_light() | {
            'surrender_account', 'eligibility_rule', 'rule'}

    @fields.depends('rule')
    def on_change_rule(self):
        if self.rule is None:
            self.surrender_account = None
            self.eligibility_rule = None
