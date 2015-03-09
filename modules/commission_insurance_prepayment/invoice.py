from itertools import groupby

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

        key = lambda c: c._group_to_agent_option_key()
        commissions.sort(key=key)
        agent_options = {}
        for key, comms in groupby(commissions, key=key):
            key = dict(key)
            agent_options[(key['agent'].id, key['option'].id)] = list(comms)

        if not agent_options:
            return commissions
        outstanding_prepayment = Agent.outstanding_prepayment(
            agent_options.keys())
        for k, v in agent_options.iteritems():
            for commission in v:
                prepayment_used = min(outstanding_prepayment[k],
                    commission.amount)
                commission.amount -= prepayment_used
                commission.redeemed_prepayment = prepayment_used
                outstanding_prepayment[k] -= prepayment_used
        return commissions

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, invoices):
        with Transaction().set_context(cancel_invoices=True):
            super(Invoice, cls).cancel(invoices)
