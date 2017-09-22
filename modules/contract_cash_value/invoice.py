# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.tools import grouped_slice
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.model import Workflow

from trytond.modules.coog_core import model, fields

__all__ = [
    'Invoice',
    'InvoiceLine',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    deposits = fields.Function(
        fields.Many2Many('contract.deposit', None, None, 'Deposit'),
        'getter_deposits')

    @classmethod
    def getter_deposits(cls, invoices, name):
        deposit = Pool().get('contract.deposit').__table__()
        cursor = Transaction().connection.cursor()

        result = {x.id: [] for x in invoices}

        for invoices_slice in grouped_slice(invoices):
            cursor.execute(*deposit.select(deposit.id, deposit.invoice,
                    where=deposit.invoice.in_([x.id for x in invoices_slice])))
            for deposit, invoice in cursor.fetchall():
                result[invoice].append(deposit)
        return result

    @classmethod
    @model.CoogView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        Deposit = Pool().get('contract.deposit')
        super(Invoice, cls).post(invoices)
        deposits = []
        for invoice in invoices:
            deposits += invoice.create_deposits()
        if deposits:
            Deposit.save(deposits)

    def create_deposits(self):
        if not self.contract or not self.contract.is_cash_value:
            return []
        if self.deposits:
            return []
        deposits = []
        for line in self.lines:
            if not line.details or not line.details[0].coverage:
                continue
            coverage = line.details[0].coverage
            if not coverage.is_cash_value:
                continue
            deposits.append(line.new_deposit())
        return deposits

    @classmethod
    @model.CoogView.button
    @Workflow.transition('paid')
    def paid(cls, invoices):
        Deposit = Pool().get('contract.deposit')
        super(Invoice, cls).paid(invoices)
        deposits_by_date = defaultdict(list)
        for invoice in invoices:
            if invoice.deposits:
                deposits_by_date[invoice.reconciliation_date] += \
                    invoice.deposits
        if deposits_by_date:
            Deposit.write(*sum([[v, {'date': k, 'state': 'received'}]
                        for k, v in deposits_by_date.items()], []))


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'

    def new_deposit(self):
        Deposit = Pool().get('contract.deposit')
        deposit = Deposit()
        deposit.state = 'draft'
        deposit.contract = self.invoice.contract
        deposit.coverage = self.details[0].coverage
        deposit.invoice = self.invoice
        deposit.amount = self.unit_price
        return deposit
