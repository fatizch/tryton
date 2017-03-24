# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from itertools import groupby
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    ]


class Invoice:
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
                key['option'].parent_contract, key['option'].coverage.insurer)

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
                    commission.amount).quantize(Decimal(1) / 10 ** 8)
                commission.amount -= prepayment_used
                commission.redeemed_prepayment = prepayment_used
                outstanding_prepayment_per_contract[key] -= prepayment_used
        return commissions

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, invoices):
        with Transaction().set_context(cancel_invoices=True):
            super(Invoice, cls).cancel(invoices)
