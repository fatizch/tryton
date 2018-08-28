# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from decimal import Decimal
from itertools import groupby
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow
from trytond.transaction import Transaction
from trytond.tools import grouped_slice

from trytond.modules.commission_insurance.commission import \
    COMMISSION_AMOUNT_DIGITS

__all__ = [
    'Invoice',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    @classmethod
    def create_commissions(cls, invoices):
        pool = Pool()
        Commission = pool.get('commission')
        all_commissions = []
        for invoice in invoices:
            for line in invoice.lines:
                commissions = line.get_commissions()
                if commissions:
                    all_commissions.extend(commissions)

        all_commissions = cls.update_commissions_with_prepayment(
            all_commissions)

        Commission.save(all_commissions)
        return all_commissions

    @classmethod
    def update_commissions_with_prepayment(cls, commissions):
        pool = Pool()
        Agent = pool.get('commission.agent')

        def keyfunc(c):
            return c._group_to_agent_option_key()

        commissions.sort(key=keyfunc)
        agent_options = {}
        all_options = {}

        for key, comms in groupby(commissions, key=keyfunc):
            key = dict(key)
            if not key['option']:
                continue
            agent_options[(key['agent'].id, key['option'].id)] = list(comms)
            all_options[(key['option'].id, key['agent'].id)] = (key['agent'],
                key['option'].parent_contract,
                key['option'].coverage.get_insurer(
                    key['option'].initial_start_date))

        if not agent_options:
            return commissions
        outstanding_prepayment = Agent.outstanding_prepayment(
            agent_options.keys())

        outstanding_prepayment_per_contract = defaultdict(lambda: 0)
        for (agent_id, option_id), prepayment_amount_base in \
                outstanding_prepayment.iteritems():
            outstanding_prepayment_per_contract[
                all_options[(option_id, agent_id)]] += prepayment_amount_base[0]

        for (agent_id, option_id), comms in agent_options.iteritems():
            key = all_options[(option_id, agent_id)]
            for commission in comms:
                if key not in outstanding_prepayment_per_contract:
                    continue
                prepayment_used = min(outstanding_prepayment_per_contract[key],
                    commission.amount).quantize(
                    Decimal(10) ** -COMMISSION_AMOUNT_DIGITS)
                # Do not change the commission amount if the difference between
                # redeemed prepayment and commission amount is less than
                # 0.01 cents.
                # When the last invoice is generated, the sum of
                # redeemed prepayment
                # is lower than the expected commissions amount. This is due to
                # a rounding problem
                dif_between_com_prepayment = commission.amount - prepayment_used
                if ((abs(dif_between_com_prepayment)) < (Decimal('0.01'))):
                    prepayment_used = commission.amount
                commission.amount -= prepayment_used
                commission.redeemed_prepayment = prepayment_used
                outstanding_prepayment_per_contract[key] -= prepayment_used
        return commissions

    @classmethod
    @Workflow.transition('paid')
    def paid(cls, invoices):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        Commission = pool.get('commission')
        super(Invoice, cls).paid(invoices)
        for sub_invoices in grouped_slice(invoices):
            paid_contracts = cls.get_paid_contract_ids(sub_invoices)
            if not paid_contracts:
                continue
            commissions = Commission.search([
                    ('date', '=', None),
                    ('is_prepayment', '=', True),
                    ('agent.plan.prepayment_due_at_first_paid_invoice',
                        '=', True),
                    ('commissioned_contract', 'in', paid_contracts)
                    ])
            Commission.write(commissions, {
                    'date': today,
                    })

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        super(Invoice, cls).post(invoices)
        for sub_invoices in grouped_slice(invoices):
            contract_invoices = [x for x in sub_invoices if x.contract]
            if contract_invoices:
                cls.unset_prepayment_date(contract_invoices)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, invoices):
        with Transaction().set_context(cancel_invoices=True):
            super(Invoice, cls).cancel(invoices)
            contract_invoices = [x for x in invoices if x.contract]
            if contract_invoices:
                cls.unset_prepayment_date(contract_invoices)

    @classmethod
    def unset_prepayment_date(cls, invoices):
        invoices = list(invoices)
        pool = Pool()
        Commission = pool.get('commission')
        all_contracts = [x.contract.id for x in invoices if x.contract]
        paid_contracts = cls.get_paid_contract_ids(invoices)
        unpaid_contracts = list(set(all_contracts) - set(paid_contracts))
        if not unpaid_contracts:
            return

        prepayment_commissions = Commission.search([
                ('invoice_line', '=', None),
                ('is_prepayment', '=', True),
                ('agent.plan.prepayment_due_at_first_paid_invoice',
                    '=', True),
                ('commissioned_contract', 'in', unpaid_contracts)],
                order=[('commissioned_contract', 'ASC'), ('agent', 'ASC')]
                )

        def keyfunc(x):
            return (x.commissioned_contract, x.agent)

        not_to_invoice = []
        for key, coms in groupby(prepayment_commissions, key=keyfunc):
            by_date = sorted(list(coms),
                key=lambda x: (x.date or datetime.date.min))
            first = by_date[0]
            if first.date:
                not_to_invoice.append(first)

        if not_to_invoice:
            Commission.write(not_to_invoice, {
                    'date': None,
                    })

    @classmethod
    def get_paid_contract_ids(cls, invoices):
        pool = Pool()
        contract_invoice = pool.get('contract.invoice').__table__()
        contract_invoice2 = pool.get('contract.invoice').__table__()
        invoice = cls.__table__()
        cursor = Transaction().connection.cursor()
        query = contract_invoice.join(invoice,
            condition=(
                (contract_invoice.invoice == invoice.id) &
                (invoice.state == 'paid')
                )
            ).join(contract_invoice2,
                condition=(
                    (contract_invoice2.contract == contract_invoice.contract) &
                    (contract_invoice2.invoice.in_([x.id for x in invoices]))
                )
            ).select(contract_invoice2.contract,
                group_by=contract_invoice2.contract)
        cursor.execute(*query)
        return [x for x, in cursor.fetchall()]
