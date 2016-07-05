# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import Unique

from trytond.modules.cog_utils import fields, model, coop_string
from trytond.modules.rule_engine import get_rule_mixin

__metaclass__ = PoolMeta
__all__ = [
    'Plan',
    'CommissionRecoveryRule',
    'Commission',
    ]


class Plan:
    __name__ = 'commission.plan'

    commission_recovery = fields.Many2One('commission.plan.recovery_rule',
        'Recovery Rule', ondelete='RESTRICT')

    def compute_recovery(self, option, agent):
        if not self.commission_recovery:
            return
        return self.commission_recovery.compute_recovery(option, agent)


class CommissionRecoveryRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoopSQL, model.CoopView):
    'Commission Recovery Rule'

    __name__ = 'commission.plan.recovery_rule'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)

    @classmethod
    def __setup__(cls):
        super(CommissionRecoveryRule, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]
        cls.rule.required = True

    def compute_recovery(self, option, agent):
        args = {}
        option.init_dict_for_rule_engine(args)
        # initial_start_date used if contract is never in force
        args['date'] = option.end_date or option.initial_start_date
        args['agent'] = agent
        return self.calculate_rule(args)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class Commission:
    __name__ = 'commission'

    is_recovery = fields.Boolean('Is Recovery Commission')

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls._error_messages.update({
                'recovery_commission': 'Recovery Commission',
                })

    @classmethod
    def _get_origin(cls):
        return super(Commission, cls)._get_origin() + ['contract.option']

    def _group_to_invoice_line_key(self):
        key = super(Commission, self)._group_to_invoice_line_key()
        return key + (('is_recovery', self.is_recovery),)

    @classmethod
    def _get_invoice_line(cls, key, invoice, commissions):
        invoice_line = super(Commission, cls)._get_invoice_line(key, invoice,
            commissions)
        if invoice_line and key['is_recovery']:
            invoice_line.description = cls.raise_user_error(
                    'recovery_commission', raise_exception=False)
        return invoice_line
