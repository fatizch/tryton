from itertools import groupby

from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.model import ModelView
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, utils

__all__ = ['CreateInvoicePrincipal', 'CreateInvoicePrincipalAsk']


class CreateInvoicePrincipal(Wizard):
    'Create Invoice Principal'
    __name__ = 'commission.create_invoice_principal'
    start_state = 'ask'
    ask = StateView('commission.create_invoice_principal.ask',
        'commission_insurer.commission_create_invoice_principal_ask_view_form',
        [Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('account_invoice.act_invoice_form')

    def get_domain(self, account):
        return [
            ('account', '=', account.id),
            ('principal_invoice_line', '=', None),
            ('journal.type', '!=', 'commission'),
            ['OR',
                [('origin.id', '!=', None, 'account.invoice')],
                [('origin.id', '!=', None, 'account.move')]
            ]]

    def create_insurer_notice(self, party):
        pool = Pool()
        Line = pool.get('account.move.line')
        Move = pool.get('account.move')
        Commission = pool.get('commission')
        Invoice = pool.get('account.invoice')

        account = party.insurer_role[0].waiting_account
        if not account:
            return
        commission_invoice = self.get_invoice(party)
        commission_invoice.save()

        lines = Line.search(self.get_domain(account))

        commissions = []
        selected = []
        for line in lines:
            if isinstance(line.origin, Move):
                if isinstance(line.origin.origin, Invoice):
                    invoice = line.origin.origin
                else:
                    continue
            else:
                invoice = line.origin
            if invoice.state != 'paid' and invoice.state != 'cancel':
                continue
            for i_line in invoice.lines:
                for commission in i_line.commissions:
                    if (commission.agent.party == party
                            and not commission.invoice_line):
                        commissions.append(commission)
            selected.append(line)
        commissions = list(set(commissions))

        amount = sum(l.credit - l.debit for l in selected)
        invoice_line = self.get_invoice_line(amount, account)
        invoice_line.invoice = commission_invoice
        invoice_line.save()
        Line.write(selected, {
                'principal_invoice_line': invoice_line.id,
                })

        key = lambda c: c._group_to_invoice_line_key()
        commissions.sort(key=key)
        for key, commissions in groupby(commissions, key=key):
            commissions = list(commissions)
            key = dict(key)
            invoice_line = Commission._get_invoice_line(
                key, commission_invoice, commissions)
            invoice_line.account = invoice_line.product.account_revenue_used
            invoice_line.invoice = commission_invoice
            invoice_line.save()
            Commission.write(commissions, {
                    'invoice_line': invoice_line.id,
                    })

        Invoice.update_taxes([commission_invoice])
        return commission_invoice

    def do_create_(self, action):
        Invoice = Pool().get('account.invoice')
        invoices = []
        for insurer in self.ask.insurers:
            commission_invoice = self.create_insurer_notice(insurer)
            if commission_invoice:
                invoices.append(commission_invoice)

        if self.ask.post_invoices:
            Invoice.post(invoices)
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', [x.id for x in invoices])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}

    def get_invoice(self, party):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        company = self.ask.company
        return Invoice(
            company=company,
            type='in_invoice',
            journal=self.ask.journal,
            party=party,
            invoice_address=party.address_get(type='invoice'),
            currency=company.currency,
            account=party.account_payable,
            payment_term=party.supplier_payment_term,
            invoice_date=utils.today(),
            )

    def get_invoice_line(self, amount, account):
        pool = Pool()
        Line = pool.get('account.invoice.line')

        line = Line()
        line.type = 'line'
        line.quantity = 1
        line.unit_price = amount
        line.account = account
        line.description = self.ask.description

        # XXX taxes?
        return line


class CreateInvoicePrincipalAsk(ModelView):
    'Create Invoice Principal'
    __name__ = 'commission.create_invoice_principal.ask'
    company = fields.Many2One('company.company', 'Company', required=True)
    insurers = fields.Many2Many('party.party', None, None, 'Insurers',
        required=True, domain=[('is_insurer', '=', True)])
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    description = fields.Text('Description', required=True)
    post_invoices = fields.Boolean('Post Invoices')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_journal():
        pool = Pool()
        Journal = pool.get('account.journal')
        journals = Journal.search([
                ('type', '=', 'commission'),
                ], limit=1)
        if journals:
            return journals[0].id

    @staticmethod
    def default_description():
        Translation = Pool().get('ir.translation')
        return Translation.get_source('received_premiums', 'error',
            Transaction().language)
