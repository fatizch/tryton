import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta, Pool
from trytond.model import dualmethod

from trytond.modules.cog_utils import fields


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

    def finalize_contract(self):
        super(Contract, self).finalize_contract()
        self.create_prepayment_commissions(adjustement=False)

    def rebill(self, at_date=None):
        super(Contract, self).rebill(at_date)
        self.create_prepayment_commissions(adjustement=True)


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
        end_first_year = min(self.start_date + relativedelta(years=1) -
            relativedelta(days=1), self.end_date or datetime.date.max)
        lines = []
        for premium in self.premiums:
            lines.extend(premium.get_invoice_lines(self.start_date,
                end_first_year))
        first_year_premium = sum([line.unit_price for line in lines])
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
            rate = (amount / pattern['first_year_premium'] * 100).quantize(
                Decimal('.01'))
        else:
            rate = None
        return amount, rate

    def compute_prepayment(self, adjustment):
        pool = Pool()
        Commission = pool.get('commission')
        Agent = pool.get('commission.agent')

        commissions = []
        agents_plans_to_compute = []
        to_delete = []
        for agent_plan in self.agent_plans_used():
            if (adjustment and agent_plan[1].adjust_prepayment or
                    not adjustment):
                agents_plans_to_compute.append(agent_plan)
        paid_prepayments = Agent.paid_prepayments([(x[0].id, self.id)
                for x in agents_plans_to_compute])
        for agent, plan in agents_plans_to_compute:
            amount, rate = self._get_prepayment_amount_and_rate(agent, plan)
            if amount is None:
                continue

            to_delete += Commission.search([
                    ('invoice_line', '=', None),
                    ('origin', '=', '%s,%s' % (self.__name__, self.id)),
                    ('is_prepayment', '=', True),
                    ('agent', '=', agent.id)
                    ])

            if (agent.id, '%s,%s' % (self.__name__, self.id)) in \
                    paid_prepayments:
                amount = amount - paid_prepayments[(agent.id, '%s,%s' % (
                            self.__name__, self.id))]
            digits = Commission.amount.digits
            amount = amount.quantize(Decimal(str(10.0 ** -digits[1])))
            if not amount:
                continue

            payment_schedule = plan.compute_prepayment_schedule(self)
            for (date, percentage) in payment_schedule:
                commission = Commission()
                commission.is_prepayment = True
                commission.date = date
                commission.origin = self
                commission.agent = agent
                commission.product = plan.commission_product
                commission.commission_rate = rate
                commission.amount = percentage * amount
                commissions.append(commission)

        Commission.delete(to_delete)
        return commissions
