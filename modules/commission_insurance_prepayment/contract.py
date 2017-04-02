# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta, Pool
from trytond.model import dualmethod
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields
from trytond.modules.commission_insurance.commission import \
    COMMISSION_AMOUNT_DIGITS, COMMISSION_RATE_DIGITS

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption'
    ]


class Contract:
    __name__ = 'contract'

    @dualmethod
    def create_prepayment_commissions(cls, contracts, adjustement):
        pool = Pool()
        Commission = pool.get('commission')
        commissions = []
        options = []
        for contract in contracts:
            options.extend(list(contract.covered_element_options +
                contract.options))
        for option in options:
            commissions.extend(option.compute_prepayment(adjustement))

        Commission.save(commissions)

    @dualmethod
    def adjust_prepayment_commissions_once_terminated(cls, contracts):
        pool = Pool()
        Commission = pool.get('commission')
        commissions = []
        options = []
        cls.remove_unpaid_reedemed_prepayment(contracts)
        for contract in contracts:
            options.extend(list(contract.covered_element_options +
                contract.options))
        for option in options:
            commissions.extend(option.adjust_prepayment_once_terminated())
        Commission.save(commissions)

    @classmethod
    def remove_unpaid_reedemed_prepayment(cls, contracts):
        pool = Pool()
        Configuration = pool.get('offered.configuration')
        Commission = pool.get('commission')
        configuration = Configuration.get_singleton()
        if not configuration:
            return

        contracts = [contract for contract in contracts
            if contract.termination_reason in
            configuration.remove_commission_for_sub_status]
        if not contracts:
            return
        options = []
        for contract in contracts:
            options += contract.options
            options += contract.covered_element_options
        commissions = Commission.search([
                ('redeemed_prepayment', '!=', None),
                ('redeemed_prepayment', '!=', 0),
                ('date', '=', None),
                ('commissioned_option', 'in', [o.id for o in options])])
        to_delete = []
        to_save = []
        for commission in commissions:
            if commission.agent.plan.delete_unpaid_prepayment:
                to_delete.append(commission)
            else:
                commission.amount += commission.redeemed_prepayment
                commission.redeemed_prepayment = None
                to_save.append(commission)
        Commission.delete(to_delete)
        Commission.save(to_save)

    def rebill(self, start=None, end=None, post_end=None):
        super(Contract, self).rebill(start, end, post_end)
        if self.termination_reason or self.status == 'void':
            self.adjust_prepayment_commissions_once_terminated()
        else:
            self.create_prepayment_commissions(adjustement=True)

    @classmethod
    def reactivate(cls, contracts):
        super(Contract, cls).reactivate(contracts)
        # Force prepayment recalculation
        cls.create_prepayment_commissions(contracts, adjustement=False)


class ContractOption:
    __name__ = 'contract.option'

    first_year_premium = fields.Function(
        fields.Numeric('Premium'),
        'get_first_year_premium')

    def agent_plans_used(self):
        "List of agent, plan tuple"
        used = []
        if self.parent_contract.agent:
            used.append((self.parent_contract.agent,
                self.parent_contract.agent.plan))
        insurer = self.parent_contract.find_insurer_agent(
            coverage=self.coverage)
        if insurer:
            used.append((insurer, insurer.plan))
        return used

    def get_first_year_premium(self, name):
        if not self.start_date:
            # when a contract is void for example
            return 0
        contract_start_date = self.parent_contract.initial_start_date
        end_first_year = contract_start_date + relativedelta(years=1, days=-1)
        lines = []
        periods = self.parent_contract.get_invoice_periods(end_first_year,
            contract_start_date)
        for premium in self.premiums:
            for start, end, _ in periods:
                if end < premium.start or (premium.end and start > premium.end):
                    continue
                lines.extend(premium.get_invoice_lines(
                        max(premium.start, start),
                        min(end, end_first_year)))
        first_year_premium = sum([
                self.parent_contract.currency.round(line.unit_price)
                for line in lines])
        return first_year_premium

    def _get_prepayment_amount_and_rate(self, agent, plan, pattern=None):
        pattern = {
            'first_year_premium': self.first_year_premium,
            'coverage': self.coverage,
            'agent': agent,
            'option': self,
            }
        amount = plan.compute_prepayment(self.product, pattern=pattern)
        if amount:
            rate = (amount / pattern['first_year_premium']).quantize(
                Decimal(10) ** -COMMISSION_RATE_DIGITS)
        else:
            rate = None
        return amount, rate

    def compute_commission_with_prepayment_schedule(self, agent, plan, rate,
            amount):
        pool = Pool()
        Commission = pool.get('commission')
        commissions = []
        if amount is None or not amount.quantize(
                Decimal(10) ** -COMMISSION_AMOUNT_DIGITS):
            return commissions
        for (date, percentage) in plan.compute_prepayment_schedule(self, agent):
            commission = Commission()
            commission.is_prepayment = True
            commission.date = date
            commission.origin = self
            commission.agent = agent
            commission.product = plan.commission_product
            commission.commission_rate = (rate * percentage).quantize(
                Decimal(10) ** -COMMISSION_RATE_DIGITS)
            commission.amount = (percentage * amount).quantize(
                Decimal(10) ** -COMMISSION_AMOUNT_DIGITS)
            commission.commissioned_option = self
            commissions.append(commission)
        return commissions

    def compute_prepayment(self, adjustment):
        pool = Pool()
        Agent = pool.get('commission.agent')
        commissions = []
        with ServerContext().set_context(prepayment_adjustment=adjustment):
            agents_plans_to_compute = self.agent_plans_used()

            if not agents_plans_to_compute:
                return []
            all_prepayments = Agent.sum_of_prepayments([(x[0].id, self.id)
                    for x in agents_plans_to_compute])
            for agent, plan in agents_plans_to_compute:
                if ((agent.id, self.id) in all_prepayments and
                        not plan.adjust_prepayment and adjustment):
                    continue
                amount, rate = self._get_prepayment_amount_and_rate(agent, plan)
                if amount is None:
                    continue

                if (agent.id, self.id) in all_prepayments:
                    amount = amount - all_prepayments[(agent.id, self.id)][0]
                commissions += self.compute_commission_with_prepayment_schedule(
                    agent, plan, rate, amount)
        return commissions

    def adjust_prepayment_once_terminated(self):
        pool = Pool()
        Agent = pool.get('commission.agent')

        commissions = []
        with ServerContext().set_context(prepayment_adjustment=True):
            agents_plans_to_compute = self.agent_plans_used()
            outstanding_prepayment = Agent.outstanding_prepayment(
                [(x[0].id, self.id) for x in agents_plans_to_compute])
            for agent, plan in agents_plans_to_compute:
                if (agent.id, self.id) not in outstanding_prepayment:
                    continue
                amount, base_amount = outstanding_prepayment[
                    (agent.id, self.id)]
                rate = amount / base_amount if base_amount else 0
                commissions += self.compute_commission_with_prepayment_schedule(
                    agent, plan, rate, -amount)
            return commissions
