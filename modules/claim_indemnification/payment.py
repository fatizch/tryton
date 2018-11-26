# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.model import Workflow

from trytond.modules.coog_core import model


__all__ = [
    'Payment',
    'PaymentCreation',
    ]


class Payment(metaclass=PoolMeta):
    __name__ = 'account.payment'

    @classmethod
    @model.CoogView.button
    @Workflow.transition('succeeded')
    def succeed(cls, payments):
        super(Payment, cls).succeed(payments)
        parties = list({x.party for x in payments if not x.line.reconciliation
            and x.kind == 'payable' and x.line.origin and
            x.line.origin.__name__ == 'account.invoice' and
            x.line.origin.business_kind == 'claim_invoice'})
        if parties:
            Pool().get('party.party').reconcile(parties)

    def get_invoice_indemn_details_per_claim_and_service(self):
        """
        Mainly used for report generation
        """
        if (not self.line or not self.line.origin_item or
                self.line.origin_item.__name__ != 'account.invoice' or
                self.line.origin_item.business_kind != 'claim_invoice'):
            return None, None, None

        Invoice = Pool().get('account.invoice')
        main_invoice = self.line.origin_item
        invoices = [main_invoice]
        if self.line.reconciliation:
            for cur_line in self.line.reconciliation.lines:
                if (cur_line.origin_item and
                        cur_line.origin_item.__name__ == 'account.invoice' and
                        cur_line.origin_item.business_kind == 'claim_invoice'):
                    invoices.append(cur_line.origin_item)
        else:
            if main_invoice.total_amount != self.amount:
                possible_invoices = Invoice.search([
                        ('party', '=', main_invoice.party.id),
                        ('state', '=', 'posted'),
                        ('business_kind', '=', 'claim_invoice')])

                if (sum(i.total_amount for i in possible_invoices) ==
                        self.amount):
                    invoices.extend(possible_invoices)
        invoices = set(invoices)

        all_details = defaultdict(tuple)
        for invoice in invoices:
            for claim, service, details in \
                    invoice.get_invoice_indemn_details_per_claim_and_service():
                all_details[(claim, service)] += details
        return {(k[0], k[1], v) for k, v in list(all_details.items())}


class PaymentCreation(metaclass=PoolMeta):
    __name__ = 'account.payment.creation'

    @classmethod
    def get_possible_journals(cls, lines, kind=None):
        '''
        Here, we return only one possible journal (Journal mix is not allowed
        because the related product defines the payment journal to use)
        '''
        if not any(x._line_from_claim_invoices() for x in lines):
            return super(PaymentCreation, cls).get_possible_journals(lines,
                kind)
        Line = Pool().get('account.move.line')
        payment_journals = Line.get_configuration_journals_from_lines(lines)
        if payment_journals:
            return [payment_journals[0]] if payment_journals else []
        return []
