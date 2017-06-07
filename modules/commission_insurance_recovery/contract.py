# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Column, Literal
from sql.operators import Or
from sql.aggregate import Sum

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.server_context import ServerContext

from trytond.modules.coog_core import utils

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    ]


class Contract:
    __name__ = 'contract'

    @classmethod
    def reactivate(cls, contracts):
        pool = Pool()
        Option = pool.get('contract.option')
        super(Contract, cls).reactivate(contracts)
        options = [option for contract in contracts
            for option in contract.options + contract.covered_element_options]
        Option._compute_commission_recovery(options)

    def calculate_commission_recovery(self, caller=None):
        # Used by configuration : endorsement
        pool = Pool()
        Option = pool.get('contract.option')
        Option._compute_commission_recovery(
            self.options + self.covered_element_options)

    def rebill(self, start=None, end=None, post_end=None):
        super(Contract, self).rebill(start, end, post_end)
        if self.status in ['void', 'terminated']:
            self.calculate_commission_recovery()

    @classmethod
    def do_terminate(cls, contracts):
        super(Contract, cls).do_terminate(contracts)
        # recovery commission should not be computed until the contract is
        # actually terminated
        if not ServerContext().get('from_batch', False):
            return
        for contract in contracts:
            contract.calculate_commission_recovery()


class ContractOption:
    __name__ = 'contract.option'

    def recovery_agent_plans_used(self):
        'List of agent, plan tuples'
        return self.agent_plans_used()

    @classmethod
    def sum_of_existing_commission_recoveries(cls, options):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        commission = pool.get('commission').__table__()
        commissioned_option_column = Column(commission, 'commissioned_option')

        where_option = Or()
        for option in options:
            where_option.append((commissioned_option_column == option.id))

        cursor.execute(*commission.select(
            Sum(commission.amount), commission.agent,
            commission.commissioned_option,
            where=commission.is_recovery == Literal(True),
            having=where_option,
            group_by=[commission.agent, commission.commissioned_option]))

        res = {}
        for amount, agent, origin in cursor.fetchall():
            res[(agent, origin)] = amount
        return res

    @classmethod
    def _compute_commission_recovery(cls, options):
        pool = Pool()
        Commission = pool.get('commission')
        today = utils.today()
        commissions = []

        active_options = []
        terminated_options = []
        for option in options:
            if (option.manual_end_date or
                    option.parent_contract.status == 'terminated' or
                    option.parent_contract.termination_reason):
                terminated_options.append(option)
            else:
                active_options.append(option)

        recoveries = cls.sum_of_existing_commission_recoveries(
            terminated_options)
        for option in terminated_options:
            for agent, plan in option.recovery_agent_plans_used():
                existing_recovery_amount = recoveries.get((agent.id,
                    option.id), 0)
                recovery_amount = plan.compute_recovery(option, agent)
                if (recovery_amount and
                        existing_recovery_amount != recovery_amount):
                    commission = Commission()
                    commission.date = today
                    commission.origin = option
                    commission.agent = agent
                    commission.is_recovery = True
                    commission.product = plan.commission_product
                    commission.commissioned_option = option
                    commission.amount = -recovery_amount + \
                        existing_recovery_amount
                    commissions.append(commission)
        Commission.save(commissions)

        if not active_options:
            return
        where_option = [option.id for option in active_options]
        to_delete = Commission.search([
                ('commissioned_option', 'in', where_option),
                ('invoice_line', '=', None),
                ('is_recovery', '=', True)
                ])
        to_cancel = Commission.search([
                ('commissioned_option', 'in', where_option),
                ('invoice_line', '!=', None),
                ('is_recovery', '=', True)
                ])
        Commission.delete(to_delete)
        for commission in Commission.copy(to_cancel):
            commission.amount *= -1
