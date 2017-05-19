# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from decimal import Decimal
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta, Pool
from trytond.model import dualmethod
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields, utils
from trytond.modules.commission_insurance.commission import \
    COMMISSION_AMOUNT_DIGITS, COMMISSION_RATE_DIGITS
from trytond.modules.coog_core.coog_date import FREQUENCY_CONVERSION_TABLE

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption'
    ]


class Contract:
    __name__ = 'contract'

    @dualmethod
    def create_prepayment_commissions(cls, contracts, adjustement,
            start_date=None, end_date=None):
        pool = Pool()
        Commission = pool.get('commission')
        commissions = []
        for contract in contracts:
            if not start_date and not end_date:
                # This is the case of first year prepayment when there is no
                # adjustment to make
                start_date = contract.initial_start_date
                end_date = start_date + relativedelta(years=1, days=-1)
            options = list(contract.covered_element_options + contract.options)
            for option in options:
                commissions.extend(option.compute_prepayment(adjustement,
                        start_date, end_date))
        Commission.save(commissions)

    @dualmethod
    def adjust_prepayment_commissions_once_terminated(cls, contracts,
            start_date, end_date):
        pool = Pool()
        Commission = pool.get('commission')
        commissions = []
        options = []
        cls.remove_unpaid_reedemed_prepayment(contracts)
        for contract in contracts:
            options.extend(list(contract.covered_element_options +
                contract.options))
        for option in options:
            commissions.extend(option.adjust_prepayment_once_terminated(
                    start_date, end_date))
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
        start_date = start if start and start != datetime.date.min else \
            self.initial_start_date
        end_date = end or min(
            (self.final_end_date or self.end_date or datetime.date.max),
            (self.initial_start_date + relativedelta(years=1, days=-1) if
                self.initial_start_date else datetime.date.max))
        end_date = end_date if end_date != datetime.date.max else None
        super(Contract, self).rebill(start, end, post_end)
        if self.status in ['void', 'terminated']:
            start_date = min(start_date, self.final_end_date
                or datetime.date.max)
            self.adjust_prepayment_commissions_once_terminated(start_date,
                end_date)
        else:
            self.create_prepayment_commissions(adjustement=True,
                start_date=start_date, end_date=end_date)

    @classmethod
    def reactivate(cls, contracts):
        super(Contract, cls).reactivate(contracts)
        # Force prepayment recalculation
        cls.create_prepayment_commissions(contracts, adjustement=False,
            start_date=None, end_date=None)

    @classmethod
    def do_terminate(cls, contracts):
        super(Contract, cls).do_terminate(contracts)
        if not ServerContext().get('from_batch', False):
            return
        for contract in contracts:
            contract.adjust_prepayment_commissions_once_terminated(
                contract.final_end_date, contract.final_end_date)


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
        results = plan.compute_prepayment(self.product, pattern=pattern)
        if type(results) is tuple:
            amount, rate = (
                Decimal(results[0] if results[0] is not None else 0),
                Decimal(results[1] if results[1] is not None else 0))
        else:
            amount = Decimal(results if results is not None else 0)
            if amount:
                rate = (amount / pattern['first_year_premium']).quantize(
                    Decimal(10) ** -COMMISSION_RATE_DIGITS)
            else:
                rate = Decimal(0)
        return amount, rate

    def get_com_premiums(self, start_date, end_date):
        premiums = utils.get_good_versions_at_date(self, 'premiums', start_date,
            'start', 'end')
        extra_premiums = utils.get_good_versions_at_date(self, 'extra_premiums',
            start_date, 'start', 'end')
        if premiums:
            premiums.sort(key=lambda x: x.start)
            latest_premium = premiums[-1]
            if latest_premium.frequency in ['yearly', 'monthly', 'quaterly',
                    'half_yearly']:
                monthly_premium_incl_tax = \
                    self.compute_premium_with_extra_premium(
                        latest_premium.amount, extra_premiums) / \
                    Decimal(FREQUENCY_CONVERSION_TABLE[
                            latest_premium.frequency])
                Tax = Pool().get('account.tax')
                InvoiceLine = Pool().get('account.invoice.line')
                monthly_premium_excl_tax = self.currency.round(
                            Tax._reverse_unit_compute(monthly_premium_incl_tax,
                                latest_premium.taxes, start_date).quantize(
                                Decimal(1) /
                                10 ** InvoiceLine.unit_price.digits[1]))
                return monthly_premium_incl_tax, monthly_premium_excl_tax
        return None, None

    def compute_commission_with_prepayment_schedule(self, agent, plan, rate,
            amount, start_date, end_date, details):
        pool = Pool()
        Commission = pool.get('commission')
        commissions = []
        if amount is None or not amount.quantize(
                Decimal(10) ** -COMMISSION_AMOUNT_DIGITS):
            return commissions
        for (date, percentage) in plan.compute_prepayment_schedule(self, agent):
            commission = Commission()
            commission.start = start_date
            commission.end = end_date
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
            commission.extra_details = details
            monthly_premium_incl_tax, monthly_premium_excl_tax = \
                self.get_com_premiums(start_date, end_date)
            commission.extra_details.update({
                'first_year_premium': self.first_year_premium,
                'is_adjustment': ServerContext().get('prepayment_adjustment',
                    False),
                'monthly_premium_incl_tax': monthly_premium_incl_tax,
                'monthly_premium_excl_tax': monthly_premium_excl_tax,
                })
            commissions.append(commission)
        return commissions

    def compute_prepayment(self, adjustment, start_date, end_date):
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
                sum_of_prepayments = 0
                if (agent.id, self.id) in all_prepayments:
                    amount = amount - all_prepayments[(agent.id, self.id)][0]
                    sum_of_prepayments = all_prepayments[(agent.id, self.id)][0]
                commissions += self.compute_commission_with_prepayment_schedule(
                    agent, plan, rate, amount, start_date, end_date,
                    {'sum_of_prepayments': sum_of_prepayments})
        return commissions

    def adjust_prepayment_once_terminated(self, start_date, end_date):
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
                amount, base_amount, details = outstanding_prepayment[
                    (agent.id, self.id)]
                _, rate = self._get_prepayment_amount_and_rate(agent, plan)
                commissions += self.compute_commission_with_prepayment_schedule(
                    agent, plan, rate, -amount, start_date, end_date, details)
            return commissions
