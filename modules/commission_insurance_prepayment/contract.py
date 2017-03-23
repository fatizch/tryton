# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta, Pool
from trytond.model import dualmethod
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields, utils


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
        for contract in contracts:
            options.extend(list(contract.covered_element_options +
                contract.options))
        for option in options:
            commissions.extend(option.adjust_prepayment_once_terminated())
        Commission.save(commissions)

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
                        max(premium.start,start),
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
                Decimal('.0001'))
        else:
            rate = None
        return amount, rate

    def compute_prepayment(self, adjustment):
        pool = Pool()
        Commission = pool.get('commission')
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
                    amount = amount - all_prepayments[(agent.id, self.id)]
                digits = Commission.amount.digits
                amount = amount.quantize(Decimal(str(10.0 ** -digits[1])))
                if not amount:
                    continue

                payment_schedule = plan.compute_prepayment_schedule(self, agent)
                for (date, percentage) in payment_schedule:
                    commission = Commission()
                    commission.is_prepayment = True
                    commission.date = date
                    commission.origin = self
                    commission.agent = agent
                    commission.product = plan.commission_product
                    commission.commission_rate = rate.quantize(
                        Decimal(1) / 10 ** 4)
                    commission.amount = percentage * amount
                    commission.commissioned_option = self
                    commissions.append(commission)
        return commissions

    def adjust_prepayment_once_terminated(self):
        pool = Pool()
        Commission = pool.get('commission')
        Agent = pool.get('commission.agent')

        commissions = []
        agents_plans_to_compute = self.agent_plans_used()
        outstanding_prepayment = Agent.outstanding_prepayment(
            [(x[0].id, self.id) for x in agents_plans_to_compute])
        for agent, plan in agents_plans_to_compute:
            if (agent.id, self.id) not in outstanding_prepayment:
                continue
            amount = outstanding_prepayment[(agent.id, self.id)]
            digits = Commission.amount.digits
            amount = amount.quantize(Decimal(str(10.0 ** -digits[1])))
            if not amount:
                continue

            commission = Commission()
            commission.is_prepayment = True
            commission.date = utils.today()
            commission.origin = self
            commission.agent = agent
            commission.product = plan.commission_product
            commission.amount = -amount
            commission.commissioned_option = self
            commissions.append(commission)
        return commissions
