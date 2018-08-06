# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from itertools import groupby
from collections import defaultdict

from decimal import Decimal
from decimal import ROUND_UP
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.model import dualmethod
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields, coog_string, model
from trytond.modules.commission_insurance.commission import \
    COMMISSION_AMOUNT_DIGITS, COMMISSION_RATE_DIGITS

__all__ = [
    'Contract',
    'ContractOption'
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    with_prepayment = fields.Function(fields.Boolean('With Prepayment'),
        'getter_with_prepayment')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'sync_prepayment': {
                    'invisible': ~Eval('with_prepayment'),
                    },
                })

    @classmethod
    @model.CoogView.button_action(
        'commission_insurance_prepayment.sync_prepayments_wizard')
    def sync_prepayment(cls, instances):
        pass

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

    def getter_with_prepayment(self, name):
        if self.agent and self.agent.plan:
            return self.agent.plan.is_prepayment

    def rebill(self, start, end=None, post_end=None):
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
        with ServerContext().set_context(reactivate=True):
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

    @classmethod
    def _group_commissions_per_party_plan(cls, com):
        return (com.commissioned_contract, com.party, com.agent)

    def _get_redeemed_commissions(self, check_date, party, agent, option=None):
        Commission = Pool().get('commission')
        domain = [
            ('commissioned_contract', '=', self.id),
            ('is_prepayment', '=', 'False'),
            ('redeemed_prepayment', '!=', None),
            ('redeemed_prepayment', '!=', Decimal('0')),
            ('party', '=', party.id),
            ('agent', '=', agent.id),
            ]
        if check_date:
            domain.append(('date', '!=', None))
        if option:
            domain.append(('commissioned_option', '=', option.id))
        return Commission.search(domain)

    def _compute_redeemed_values(self, commissions, generated_amount,
            paid_amount):
        computed_all_redeemed_amount = sum([x.redeemed_prepayment
                for x in commissions])
        return computed_all_redeemed_amount - (generated_amount +
                paid_amount)

    def _fill_deviation_errors(self, key, commissions, deviation_amount,
            paid_amount, generated_amount, computed_amount):
        codes = []
        linear_err = any((not x.is_prepayment and x.amount != 0
                and not x.invoice_line for x in commissions))
        paid_linear_amount = sum(x.amount for x in commissions if
            not x.is_prepayment and x.amount != 0 and x.invoice_line)
        paid_linear_err = paid_linear_amount and \
            abs(deviation_amount) > Decimal('0.001')
        if abs(deviation_amount) > Decimal('0.001'):
            codes.append({
                    'code': 'KO', 'description': 'The recalculated amount '
                    'is different from the total amount.'
                    })
        if linear_err:
            codes.append({
                'code': 'LIN_ERR',
                'description': 'There is linear commissions on '
                'prepayment plan.',
                })
        if paid_linear_err:
            codes.append({
                'code': 'PAID_LIN_ERR',
                'description': 'There is unbalanced paid linear commissions '
                'on prepayment plan. (%s)' % paid_linear_amount,
                })

        if (not linear_err and not paid_linear_err
                and abs(deviation_amount) <= Decimal('0.001')):
            # Everything all right
            codes.append({'code': 'OK', 'description': ''})
        else:
            if deviation_amount and self.status == 'terminated':
                # Use the redeemed prepayments when the contract is
                # terminated
                redeemed_coms = self._get_redeemed_commissions(
                    True, key[1], key[2])
                deviation_with_computed = self._compute_redeemed_values(
                    redeemed_coms, computed_amount, Decimal('0'))
                if abs(deviation_with_computed) <= Decimal('0.001'):
                    # Action: create adjustement line
                    codes.append({
                            'code': 'CNT_ADJ',
                            'description': 'The computed recalculated amount '
                            'matches the total amount when using the paid '
                            'redeemed amount (contract is terminated)'
                            })
                    return codes
                deviation_redeemed_amount = self._compute_redeemed_values(
                    redeemed_coms, generated_amount, paid_amount)
                if abs(deviation_redeemed_amount) <= Decimal('0.001'):
                    codes.append({
                            'code': 'CNT_REE',
                            'description': 'The total amount '
                            'matches with the sum of the paid '
                            'redeemed amount (contract is terminated)'
                            })
                    return codes
                all_redeemed_coms = self._get_redeemed_commissions(
                    False, key[1], key[2])
                deviation_all_redeemed_amount = self._compute_redeemed_values(
                    all_redeemed_coms, generated_amount, paid_amount)
                if abs(deviation_all_redeemed_amount) <= Decimal('0.001'):
                    codes.append({
                            'code': 'CNT_REE_UNPAID',
                            'description': 'The recalculated amount '
                            'matches the total amount when using the '
                            'redeemed amount (contract is terminated and '
                            'probably has unpaid posted invoices)',
                            })
                    return codes
                codes.append({
                    'code': 'CNT_FORCE_ADJ',
                    'description': 'The computed recalculated amount '
                    'does not match the total amount. The contract is '
                    'terminated, We should adjust according to the '
                    'recalculated amount'
                    })
            elif deviation_amount and self.status != 'terminated':
                codes.append({
                        'code': 'CNT_ACT_ADJ',
                        'description': 'The actual amount is different '
                        'from the computed amount on this active contract.'
                        'We should adjust according to the recalculated '
                        'amount',
                        })
                return codes
        return codes

    def _get_computed_amount(self, agent, per_option=False,
            paid_invoices_only=False):
        if not per_option:
            computed_amount = Decimal('0')
        else:
            computed_amount = defaultdict(lambda: Decimal(0))
        for option in self.covered_element_options:
            for agt, plan in option.agent_plans_used():
                if agent != agt:
                    continue
                pattern = {
                    'first_year_premium': option.get_first_year_premium(
                        None, limit_to_paid_invoice=True,
                        limit_for_terminated=not paid_invoices_only),
                    'coverage': option.coverage,
                    'agent': agent,
                    'option': option,
                    }
                prepayment_amount = option._get_prepayment_amount_and_rate(
                    agent, plan, pattern)[0]
                if per_option is False:
                    computed_amount += prepayment_amount
                else:
                    computed_amount[option.id] += prepayment_amount
        return computed_amount

    @classmethod
    def _group_origin_and_protocol(cls, com):
        return (com.agent, com.origin, com.start, com.end)

    def check_for_redeemned_inconsistencies(self, deviations):
        inconsistencies = []
        commissions = sum([x['commissions'] for x in deviations], [])
        commissions = [x for x in commissions
            if x.origin and x.origin.__name__ == 'account.invoice.line' and
            x.redeemed_prepayment]
        commissions = sorted(commissions, key=self._group_origin_and_protocol)
        for key, grouped_coms in groupby(commissions,
                key=self._group_origin_and_protocol):
            consistency = 0
            agent, origin, start, end = key
            grouped_coms = list(grouped_coms)
            consistency = sum([1 if x.redeemed_prepayment > 0 else -1 for x in
                    grouped_coms])
            if consistency not in (0, 1):
                if consistency > 1:
                    description = 'Too much redeemed'
                else:
                    description = 'Too few redeemed'
                inconsistencies.append({
                        'contract': self,
                        'commissions': grouped_coms,
                        'consistency': consistency,
                        'line': origin,
                        'agent': agent,
                        'start': start,
                        'end': end,
                        'description': description,
                        'code': 'KO',
                        })
        return inconsistencies

    @classmethod
    def get_prepayment_deviations(cls, contracts):
        Commission = Pool().get('commission')
        commissions = Commission.search([
                ('commissioned_contract', 'in', [x.id for x in contracts]),
                ('agent.plan.is_prepayment', '=', True),
                ])
        commissions = sorted(commissions,
            key=cls._group_commissions_per_party_plan)
        per_contracts = defaultdict(list)
        for key, grouped_commissions in groupby(commissions,
                key=cls._group_commissions_per_party_plan):
            grouped_commissions = sorted(list(grouped_commissions),
                key=lambda x: x.date or datetime.date.max)
            contract = key[0]
            computed_amount = contract._get_computed_amount(key[2])
            computed_amount_today = contract._get_computed_amount(key[2],
                paid_invoices_only=True)
            generated_amount = sum([x.amount for x in grouped_commissions
                    if not x.invoice_state])
            paid_amount = sum([x.amount for x in grouped_commissions
                    if x.invoice_state])
            deviation_amount = computed_amount - (
                generated_amount + paid_amount)
            codes = contract._fill_deviation_errors(key, grouped_commissions,
                deviation_amount, paid_amount, generated_amount,
                computed_amount)
            dates = list({coog_string.translate_value(x, 'date')
                for x in grouped_commissions if x.date and x.amount > 0})
            per_contracts[contract].append({
                    'contract': key[0],
                    'party': key[1],
                    'agent': key[2],
                    'generated_amount': generated_amount,
                    'paid_amount': paid_amount,
                    'actual_amount': generated_amount + paid_amount,
                    'theoretical_amount': computed_amount,
                    'theoretical_amount_today': computed_amount_today,
                    'deviation_amount': deviation_amount,
                    'number_of_date': len(dates),
                    'dates': dates,
                    'codes': codes,
                    'commissions': grouped_commissions,
                    })
        return per_contracts

    def _move_linear_amount_to_prepayment(self):
        Commission = Pool().get('commission')
        commissions = Commission.search([
            ('commissioned_contract', '=', self.id),
            ('is_prepayment', '=', False),
            ('agent.plan.is_prepayment', '=', True),
            ('amount', '!=', None),
            ('amount', '!=', 0),
            ('invoice_line', '=', None),
            ])
        for com in commissions:
            new_amount = (com.redeemed_prepayment or Decimal('0')) + \
                com.amount
            com.redeemed_prepayment = new_amount
            com.amount = Decimal('0')
        if commissions:
            Commission.save(commissions)

    def _create_deviation_adjustement_line(self, party, agent, deviation,
            err_code):
        Commission = Pool().get('commission')
        adjustements = []
        contract = deviation['contract']
        with ServerContext().set_context(prepayment_adjustment=True):
            options = list(self.covered_element_options)
            for option in options:
                coms = self._get_redeemed_commissions(
                    True, party, agent, option)
                redeemed_amount = Decimal(
                    sum([x.redeemed_prepayment for x in coms]))
                commissions = Commission.search([
                        ('commissioned_contract', '=', self.id),
                        ('agent.plan.is_prepayment', '=', True),
                        ('agent', '=', agent.id),
                        ('party', '=', party.id),
                        ('commissioned_option', '=', option.id),
                        ])
                generated_amount = sum([x.amount for x in commissions
                        if not x.invoice_state])
                paid_amount = sum([x.amount for x in commissions
                        if x.invoice_state])
                actual_amount = generated_amount + paid_amount
                _, rate = option._get_prepayment_amount_and_rate(agent,
                    agent.plan)
                if err_code not in ('CNT_REE', 'CNT_FORCE_ADJ',
                        'CNT_ACT_ADJ'):
                    adjustement_amount = redeemed_amount - actual_amount
                else:
                    computed_amount = contract._get_computed_amount(agent,
                        per_option=True)[option.id]
                    deviation_amount = computed_amount - (
                        generated_amount + paid_amount)
                    adjustement_amount = deviation_amount
                adjustements.extend(
                    option.compute_commission_with_prepayment_schedule(
                        agent, agent.plan, rate, adjustement_amount,
                        self.last_paid_invoice_end, self.final_end_date, {}))
            if adjustements:
                Commission.save(adjustements)

    @classmethod
    def try_adjust_prepayments(cls, deviations, codes=None, adjusted=None,
            updating=False):
        pool = Pool()
        adjusted = adjusted if adjusted is not None else []

        for deviation in deviations:
            agent = pool.get('commission.agent')(deviation['agent'])
            party = pool.get('party.party')(deviation['party'])
            contract = cls(deviation['contract'])
            working_codes = codes if codes is not None else [
                x['code'] for x in deviation['codes']]
            if 'LIN_ERR' in working_codes:
                contract._move_linear_amount_to_prepayment()
                working_codes.remove('LIN_ERR')
                adjusted.append(deviation)
                cls.try_adjust_prepayments([deviation], working_codes,
                    adjusted, True)
            codes_adj = (set(['CNT_ADJ', 'CNT_REE_UNPAID', 'CNT_REE',
                    'CNT_FORCE_ADJ', 'CNT_ACT_ADJ']) &
                set(working_codes))
            if codes_adj:
                code = next(iter(codes_adj))
                contract._create_deviation_adjustement_line(party,
                    agent, deviation, err_code=code)
                working_codes.remove(code)
                adjusted.append(deviation)
                cls.try_adjust_prepayments([deviation], working_codes,
                    adjusted, True)

        def _freeze(deviation):
            deviation['codes'] = frozenset([frozenset(c.items()) for c in
                    deviation['codes']])
            if isinstance(deviation['dates'], list):
                deviation['dates'] = frozenset(deviation['dates'])
            return frozenset(deviation.items())

        def _unfreeze(deviation):
            deviation = dict(deviation)
            deviation['codes'] = [dict(x) for x in deviation['codes']]
            dates = deviation['dates']
            deviation['dates'] = [x for x in dates] \
                if isinstance(dates, frozenset) else deviation['dates']
            return deviation

        if updating:
            return

        frozen_deviations = set(_freeze(dev) for dev in deviations)
        frozen_adjusted = set(frozenset(a.items()) for a in adjusted)
        adjusted_set = [_unfreeze(s) for s in frozen_adjusted]
        non_adjusted_set = [_unfreeze(s) for s in
            set(dev for dev in frozen_deviations
                if dev not in frozen_adjusted)]
        deviations = [_unfreeze(dev) for dev in deviations]
        return list(adjusted_set), list(non_adjusted_set), list(deviations)

    @classmethod
    def resolve_redeemed_inconsistencies(cls, inconsistencies):
        Commission = Pool().get('commission')
        per_obj = {}

        def _freeze(inconsistency):
            inconsistency['commissions'] = frozenset(
                inconsistency['commissions'])
            inconsistency = frozenset(inconsistency.items())
            return inconsistency

        def _unfreeze(inconsistency):
            inconsistency = dict(inconsistency)
            inconsistency['commissions'] = [x for x in
                inconsistency['commissions']]
            return inconsistency

        for obj in inconsistencies:
            commissions = iter(sorted(obj['commissions'],
                key=lambda x: x.create_date))
            key = _freeze(obj)
            per_obj[key] = []
            # commissions is an iterator so this zip allow us to iterate over
            # commissions two by two in a sexy way
            for com1, com2 in zip(commissions, commissions):
                if (abs(com1.redeemed_prepayment) !=
                        abs(com2.redeemed_prepayment)):
                    obj['description'] = 'Manual action required (could not '\
                        'automatically cancel redeemed together)'
                    # Ignore all the line commissions
                    per_obj[key] = []
                    break
                if (com1.amount.quantize(Decimal('.0001'),
                            rounding=ROUND_UP) != Decimal(0) or
                        com2.amount.quantize(Decimal('.0001'),
                            rounding=ROUND_UP) != Decimal(0)):
                    obj['description'] = 'Manual action required (redeemed '\
                        ' with commission amount)'
                    # Ignore all the line commissions
                    per_obj[key] = []
                    break
                if com1.redeemed_prepayment + com2.redeemed_prepayment == 0:
                    continue
                else:
                    com1.redeemed_prepayment = abs(com1.redeemed_prepayment)
                    com2.redeemed_prepayment = (com2.redeemed_prepayment * -1
                        if com2.redeemed_prepayment > 0
                        else com2.redeemed_prepayment)
                per_obj[key].extend([com1, com2])
        to_save = sum(per_obj.values(), [])
        if to_save:
            Commission.save(to_save)

        return [_unfreeze(k) for k, v in per_obj.items() if v], [
            _unfreeze(k) for k, v in per_obj.items() if not v], [
            _unfreeze(x) for x in per_obj.keys()]

    @classmethod
    def _add_prepayment_deviations_description(cls, deviations):
        for deviation in deviations:
            deviation['description'] = '\n'.join([x['description']
                    for x in deviation['codes']])
            deviation['codes'] = '\n'.join([x['code']
                    for x in deviation['codes']])


class ContractOption:
    __metaclass__ = PoolMeta
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
        insurer = self.parent_contract.find_insurer_agent(option=self)
        if insurer:
            used.append((insurer, insurer.plan))
        return used

    def get_first_year_premium(self, name, limit_to_paid_invoice=False,
            limit_for_terminated=True):
        if not self.start_date:
            # when a contract is void for example
            return 0
        contract_start_date = self.parent_contract.initial_start_date
        end_first_year = contract_start_date + relativedelta(years=1, days=-1)
        if ((limit_to_paid_invoice and
                   self.parent_contract.status == 'terminated') or
                (limit_to_paid_invoice and not limit_for_terminated)):
            if not self.parent_contract.last_paid_invoice_end:
                return 0
            end_first_year = self.parent_contract.last_paid_invoice_end
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
        pattern = pattern or {
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
            commission.commissioned_contract = self.parent_contract
            commission.extra_details = details
            commission.extra_details.update({
                'first_year_premium': self.first_year_premium,
                'is_adjustment': ServerContext().get('prepayment_adjustment',
                    False),
                'monthly_premium_incl_tax': self.monthly_premium_incl_tax,
                'monthly_premium_excl_tax': self.monthly_premium_excl_tax,
                })
            commissions.append(commission)
        if commissions and agent.plan.prepayment_due_at_first_paid_invoice:
            first_date_com = sorted(commissions, key=lambda x: x.date)[0]
            first_date_com.date = None
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
                        not plan.adjust_prepayment and adjustment
                        and not ServerContext().get('reactivate', False)):
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
