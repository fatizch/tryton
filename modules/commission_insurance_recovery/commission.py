# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.aggregate import Sum
from sql.operators import Or, Not

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.model import Unique

from trytond.modules.coog_core import fields, model, coog_string
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'Plan',
    'CommissionRecoveryRule',
    'Commission',
    'Agent',
    'CommissionDescriptionConfiguration',
    ]


class Plan(metaclass=PoolMeta):
    __name__ = 'commission.plan'

    commission_recovery = fields.Many2One('commission.plan.recovery_rule',
        'Recovery Rule', ondelete='RESTRICT')

    def compute_recovery(self, option, agent):
        if not self.commission_recovery:
            return
        pattern = self.recovery_pattern(option, agent)
        for line in self.lines:
            if line.match(pattern):
                return self.commission_recovery.compute_recovery(option, agent)

    def recovery_pattern(self, option, agent):
        return {'coverage': option.coverage}


class CommissionRecoveryRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
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
        return self.calculate_rule(args, return_full=True)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)


class Commission(metaclass=PoolMeta):
    __name__ = 'commission'

    is_recovery = fields.Boolean('Is Recovery Commission', readonly=True)

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

    def get_recovery_details(self, recovery_info, recovery_amount,
            existing_recovery_amount):
        if self.is_recovery:
            recovery_details = {
                'recovery_amount': recovery_amount,
                'existing_recovery_amount': existing_recovery_amount,
                }
            if recovery_info and len(recovery_info) == 1:
                recovery_details.update(recovery_info[0])
            return recovery_details

    def getter_calculation_description(self, name):
        description = super().getter_calculation_description(name)
        details = self.extra_details
        if self.is_recovery and details:
            commission_title = ''
            desc_configuration = Pool().get(
                'commission.description.configuration').get_singleton()
            if (desc_configuration
                    and desc_configuration.recovery_commission_title):
                commission_title = desc_configuration.recovery_commission_title
            description += '%s\n%s = %s - %s' % (
                commission_title,
                str(self.amount) if self.amount is not None else '',
                str(details.get('existing_recovery_amount', 0)),
                str(details.get('recovery_amount', 0)))
        return description


class Agent(metaclass=PoolMeta):
    __name__ = 'commission.agent'

    @classmethod
    def commissions_until_date(cls, agents, date):
        """
            Agents is a list of tuple (agent_id, option_id)
            Return a dictionnary with (agent_id, option_id) as key
            and dictionnary with sum of contract commission amount
            without prepayment and first year commission redeemed
            amount as value
        """
        if not agents:
            return {}

        commission = Pool().get('commission').__table__()
        cursor = Transaction().connection.cursor()

        constraints = []
        result = {}
        for agent in agents:
            result[agent] = {
                'commission': 0,
                'redeemed_commission': 0
                }
            constraints.append((
                    (commission.agent == agent[0]) &
                    (commission.commissioned_option == agent[1]) &
                    (commission.end <= date) &
                    Not(commission.is_prepayment) &
                    Not(commission.is_recovery)))

        cursor.execute(*commission.select(commission.agent,
                commission.commissioned_option,
                Sum(commission.amount), Sum(commission.redeemed_prepayment),
                where=Or(constraints),
                group_by=[commission.agent, commission.commissioned_option]))
        for agent, option, com_amount, com_redeemed in cursor.fetchall():
            result[(agent, option)] = {
                'commission': com_amount or 0,
                'redeemed_commission': com_redeemed or 0
                }
        return result

    @classmethod
    def sum_of_commissions(cls, agents):
        """
            Agents is a list of tuple (agent_id, option_id)
            Return a dictionnary with (agent_id, option_id) as key
            and sum of contract commission amount with prepayment as value
        """
        if not agents:
            return {}

        commission = Pool().get('commission').__table__()
        cursor = Transaction().connection.cursor()

        constraints = []
        result = {}
        for agent in agents:
            result[agent] = 0
            constraints.append((
                    (commission.agent == agent[0]) &
                    (commission.commissioned_option == agent[1]) &
                    Not(commission.is_recovery)))

        cursor.execute(*commission.select(commission.agent,
                commission.commissioned_option, Sum(commission.amount),
                where=Or(constraints),
                group_by=[commission.agent, commission.commissioned_option]))
        for agent, option, com_amount in cursor.fetchall():
            result[(agent, option)] = com_amount
        return result


class CommissionDescriptionConfiguration(metaclass=PoolMeta):

    __name__ = 'commission.description.configuration'

    recovery_commission_title = fields.Char(
        'Recovery Commission Title', help='Contains the string which will'
        ' be used to introduce recovery commissions calculation details',
        required=True, translate=True)
