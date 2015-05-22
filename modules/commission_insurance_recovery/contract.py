from sql import Column
from sql.operators import Or
from sql.aggregate import Sum

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import utils

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    ]


class Contract:
    __name__ = 'contract'

    @classmethod
    def terminate(cls, contracts, at_date, termination_reason):
        pool = Pool()
        Option = pool.get('contract.option')
        super(Contract, cls).terminate(contracts, at_date, termination_reason)
        options = [option for contract in contracts
            for option in contract.options + contract.covered_element_options]
        Option._compute_commission_recovery(options)

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


class ContractOption:
    __name__ = 'contract.option'

    def recovery_agent_plans_used(self):
        'List of agent, plan tuples'
        used = []
        if self.parent_contract.agent:
            used.append((self.parent_contract.agent,
                self.parent_contract.agent.plan))
        insurer = self.parent_contract.find_insurer_agent(
            coverage=self.coverage)
        if insurer:
            used.append((insurer, insurer.plan))
        return used

    @classmethod
    def sum_of_existing_commission_recoveries(cls, options):
        pool = Pool()
        cursor = Transaction().cursor
        commission = pool.get('commission').__table__()
        origin_column = Column(commission, 'origin')

        where_origin = Or()
        for option in options:
            where_origin.append((origin_column == 'contract.option,' +
                    str(option.id)))

        cursor.execute(*commission.select(
            Sum(commission.amount), commission.agent, commission.origin,
            where=commission.is_recovery == True,
            having=where_origin,
            group_by=[commission.agent, commission.origin]))

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
                        'contract.option,' + str(option.id)), 0)
                recovery_amount = plan.compute_recovery(option, agent)
                if (recovery_amount and
                        existing_recovery_amount != recovery_amount):
                    commission = Commission()
                    commission.date = today
                    commission.origin = option
                    commission.agent = agent
                    commission.is_recovery = True
                    commission.product = plan.commission_product
                    commission.amount = -recovery_amount + \
                        existing_recovery_amount
                    commissions.append(commission)
        Commission.save(commissions)

        where_origin = ['contract.option,' + str(option.id) for option in
            active_options]
        to_delete = Commission.search([
                ('origin', 'in', where_origin),
                ('invoice_line', '=', None)
                ])
        to_cancel = Commission.search([
                ('origin', 'in', where_origin),
                ('invoice_line', '!=', None)
                ])
        Commission.delete(to_delete)
        for commission in Commission.copy(to_cancel):
            commission.amount *= -1
