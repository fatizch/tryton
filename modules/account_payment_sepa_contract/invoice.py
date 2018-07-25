# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, utils


__all__ = [
    'Invoice',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    sepa_mandate = fields.Function(fields.Many2One(
            'account.payment.sepa.mandate', 'Sepa Mandate',
            states={'invisible': ~Eval('sepa_mandate')}),
        'get_sepa_mandate', searcher='search_sepa_mandate')
    bank_account = fields.Function(
        fields.Many2One('bank.account', 'Bank Account',
        states={'invisible': ~Eval('bank_account')}),
        'get_bank_account')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._check_modify_exclude.append('sepa_mandate')

    def update_invoice_before_post(self):
        invoice = super(Invoice, self).update_invoice_before_post()
        if not self.contract:
            return invoice
        contract_revision_date = max(self.invoice_date, utils.today())
        with Transaction().set_context(
                contract_revision_date=contract_revision_date):
            if (self.contract.billing_information.direct_debit and
                    self.contract.billing_information.sepa_mandate):
                invoice['sepa_mandate'] = \
                    self.contract.billing_information.sepa_mandate
            else:
                invoice['sepa_mandate'] = None
            return invoice

    def get_bank_account(self, name):
        return (self.sepa_mandate.account_number.account.id
            if self.sepa_mandate else None)

    @classmethod
    def get_sepa_mandate(cls, invoices, name):
        mandate_per_invoices = {}
        for invoice in invoices:
            mandate_per_invoices[invoice.id] = None
            lines = [x for x in invoice.lines_to_pay if
                not x.reconciliation and
                (x.payment_date or x.maturity_date or datetime.date.max) >=
                utils.today()
                ]
            if lines:
                # If there are lines, sort them and get the first sepa_mandate
                lines = sorted(lines, key=lambda x: (
                    x.payment_date or x.maturity_date or datetime.date.max))
                sepa_mandate = lines[0].sepa_mandate
                if sepa_mandate:
                    mandate_per_invoices[invoice.id] = sepa_mandate.id
        return mandate_per_invoices

    @classmethod
    def search_sepa_mandate(cls, name, clause):
        assert clause[1] == '='
        return [('move.lines', 'where', [
                    [('payment_date', '!=', None)],
                    ['AND',
                        [('payments.state', 'in',
                                ['approved', 'processing', 'succeeded'])],
                        [('payments.sepa_mandate',) + tuple(clause[1:])],
                        [('contract.billing_informations.sepa_mandate',) +
                            tuple(clause[1:])]]])]
