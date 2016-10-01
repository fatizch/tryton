# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.wizard import Wizard, StateView, Button

from trytond.modules.coog_core import model, fields

__all__ = [
    'ShowAllInvoices',
    'ShowAllInvoicesMain',
    'ShowAllInvoicesLine',
    ]


class ShowAllInvoices(Wizard):
    'Show All Invoices'

    __name__ = 'contract.invoice.show_all'

    start_state = 'all_invoices'
    all_invoices = StateView('contract.invoice.show_all.show',
        'contract_loan_invoice.show_all_invoices_main_view_form', [
            Button('End', 'end', 'tryton-close', default=True)])

    def default_all_invoices(self, name):
        pool = Pool()
        assert Transaction().context.get('active_model', None) == 'contract'
        Contract = pool.get('contract')
        LineDisplayer = pool.get('contract.invoice.show_all.line')

        contract = Contract(Transaction().context.get('active_id'))
        future_invoices = Contract.get_future_invoices(contract)
        for invoice in future_invoices:
            LineDisplayer.update_detail_for_display(invoice)
        return {
            'invoices': future_invoices,
            }


class ShowAllInvoicesMain(model.CoogView):
    'Show All Invoices - Main'

    __name__ = 'contract.invoice.show_all.show'

    invoices = fields.One2Many('contract.invoice.show_all.line', None,
        'Invoices', readonly=True)


class ShowAllInvoicesLine(model.CoogView):
    'Show All Invoices - Line'

    __name__ = 'contract.invoice.show_all.line'

    name = fields.Char('Name', readonly=True)
    premium = fields.Many2One('contract.premium', 'Premium', readonly=True)
    start = fields.Date('Start', readonly=True)
    end = fields.Date('End', readonly=True)
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    tax_amount = fields.Numeric('Tax Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    total_amount = fields.Numeric('Total Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    currency_digits = fields.Integer('Currency Digits', readonly=True)
    currency_symbol = fields.Char('Currency Symbol', readonly=True)
    details = fields.One2Many('contract.invoice.show_all.line', None,
        'Details', readonly=True)
    loan = fields.Many2One('loan', 'Loan', readonly=True)

    @classmethod
    def update_detail_for_display(cls, detail):
        for sub_detail in detail.get('details', []):
            cls.update_detail_for_display(sub_detail)
        if detail['premium'] is not None:
            detail['premium.rec_name'] = detail['premium'].rec_name
            detail['premium'] = detail['premium'].id
        if detail['loan'] is not None:
            detail['loan.rec_name'] = detail['loan'].rec_name
            detail['loan'] = detail['loan'].id
