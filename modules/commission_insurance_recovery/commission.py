from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields, model, coop_string
from trytond.modules.rule_engine import RuleMixin

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


class CommissionRecoveryRule(model.CoopSQL, model.CoopView, RuleMixin):
    'Commission Recovery Rule'

    __name__ = 'commission.plan.recovery_rule'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)

    @classmethod
    def __setup__(cls):
        super(CommissionRecoveryRule, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
            ]

    def compute_recovery(self, option, agent):
        args = {}
        option.init_dict_for_rule_engine(args)
        args['agent'] = agent
        return self.calculate(args)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class Commission:
    __name__ = 'commission'

    is_recovery = fields.Boolean('Is Recovery Commission')

    def get_commissioned_option(self, name):
        if not self.is_recovery:
            return super(Commission, self).get_commissioned_option(name)
        return self.origin.id

    def get_commissioned_contract(self, name):
        if not self.is_recovery:
            return super(Commission, self).get_commissioned_contract(name)
        return self.origin.parent_contract.id

    @classmethod
    def _get_origin(cls):
        return super(Commission, cls)._get_origin() + ['contract.option']
