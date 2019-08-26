# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, utils


__all__ = [
    'MoveLine',
    ]


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    sepa_mandate = fields.Function(fields.Many2One(
            'account.payment.sepa.mandate', 'Sepa Mandate'),
        'get_sepa_mandate')
    bank_account = fields.Function(fields.Many2One(
            'bank.account', 'Bank Account'),
        'get_bank_account')

    def init_payment_information(self, journal, kind, amount, payment):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        mandate = None
        if self.contract:
            with Transaction().set_context(
                    contract_revision_date=payment['date']):
                billing_info = self.contract.billing_information \
                    if self.contract else None
                mandate = billing_info.sepa_mandate if billing_info else None
        if (not mandate and self.move_origin and
                isinstance(self.move_origin, Invoice) and
                self.move_origin.sepa_mandate):
            mandate = self.move_origin.sepa_mandate
        if mandate:
            payment['sepa_mandate'] = mandate.id
            payment['bank_account'] = mandate.account_number.account.id
        elif journal.process_method == 'sepa' and kind == 'receivable':
            payment['state'] = 'draft'
        return super(MoveLine, self).init_payment_information(journal, kind,
            amount, payment)

    @classmethod
    def get_sepa_mandate(cls, lines, name):
        sepa_mandate_per_lines = {}
        for line in lines:
            sepa_mandate_per_lines[line.id] = None
            if not line.payment_date:
                continue
            payments = list({x for x in line.payments
                    if x.state in ['approved', 'processing', 'succeeded']})
            if payments:
                payments = sorted(payments, key=lambda x: x.date, reverse=True)
                sepa_mandate_per_lines[line.id] = payments[0].sepa_mandate.id \
                    if payments[0].sepa_mandate else None
                continue
            revision_date = max(line.payment_date, utils.today())
            with Transaction().set_context(
                    contract_revision_date=revision_date):
                if line.contract:
                    billing_info = line.contract.billing_information
                    if not billing_info or not billing_info.sepa_mandate:
                        continue
                    sepa_mandate_per_lines[line.id] = \
                        billing_info.sepa_mandate.id
        return sepa_mandate_per_lines

    def get_bank_account(self, name):
        if self.sepa_mandate:
            return self.sepa_mandate.account_number.account.id
        if self.origin_item:
            if getattr(self.origin_item, 'bank_account', None):
                return self.origin_item.bank_account.id
            elif getattr(self.origin_item, 'sepa_mandate', None):
                return self.origin_item.sepa_mandate.account_number.account.id
