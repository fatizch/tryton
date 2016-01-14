from itertools import groupby
from collections import defaultdict
from sql import Null

from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.model import ModelView
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, utils, coop_date

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

    @classmethod
    def select_lines(cls, account, max_date=None):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoice = Invoice.__table__()
        move = pool.get('account.move').__table__()
        move_line = pool.get('account.move.line').__table__()
        journal = pool.get('account.journal').__table__()
        cursor = Transaction().cursor

        query_table = move_line.join(move, condition=move_line.move == move.id
            ).join(invoice,
            condition=move.id.in_([invoice.move, invoice.cancel_move])
            ).join(journal, condition=(move.journal == journal.id))

        where_clause = (
            (move_line.account == account.id)
            & (move_line.principal_invoice_line == Null)
            & (move.state == 'posted')
            & invoice.state.in_(['paid', 'cancel'])
            & (journal.type != 'commission'))
        if max_date is not None:
            where_clause &= (move.date <= max_date)

        cursor.execute(*query_table.select(invoice.id.as_('invoice'),
                move_line.id.as_('move_line'), move_line.credit.as_('credit'),
                move_line.debit.as_('debit'),
                where=where_clause, order_by=invoice.id))

        invoices_data = defaultdict(list)
        for invoice, line, credit, debit in cursor.fetchall():
            invoices_data[invoice].append((line, credit, debit))

        return Invoice.browse(invoices_data.keys()), invoices_data

    def create_insurer_notice(self, party):
        pool = Pool()
        Line = pool.get('account.move.line')
        Commission = pool.get('commission')
        Invoice = pool.get('account.invoice')

        account = party.insurer_role[0].waiting_account
        if not account:
            return

        invoices, invoices_data = self.select_lines(account,
            self.ask.until_date)

        commissions, lines, amount = [], [], 0
        for invoice in invoices:
            invoice_coms = []
            for i_line in invoice.lines:
                for commission in [x for x in i_line.commissions
                        if (x.agent.party == party and not x.invoice_line)]:
                    if (not self.ask.until_date
                            or commission.date <= self.ask.until_date):
                        invoice_coms.append(commission)
                    else:
                        break
                else:
                    continue
                break
            else:
                commissions += invoice_coms
                for line, credit, debit in invoices_data[invoice.id]:
                    lines.append(line)
                    amount += (credit or 0) - (debit or 0)
                continue

        commission_invoice = self.get_invoice(party)
        commission_invoice.save()
        if not lines and not commissions:
            return commission_invoice
        invoice_line = self.get_invoice_line(amount, account)
        invoice_line.invoice = commission_invoice
        invoice_line.save()

        Line.write(Line.browse(lines), {
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
    until_date = fields.Date('Until Date')

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

    @staticmethod
    def default_until_date():
        return coop_date.get_last_day_of_last_month(utils.today())
