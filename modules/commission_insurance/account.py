from collections import defaultdict

from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Fee',
    'MoveLine',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    broker_fee_invoice_line = fields.Many2One('account.invoice.line',
        'Broker Fee Invoice Line', readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._check_modify_exclude.add('broker_fee_invoice_line')

    @classmethod
    def copy(cls, lines, default=None):
        default.setdefault('broker_fee_invoice_line', None)
        return super(MoveLine, cls).copy(lines, default)


class Fee:
    __name__ = 'account.fee'

    broker_fee = fields.Boolean('Broker Fee')

    @classmethod
    def __setup__(cls):
        super(Fee, cls).__setup__()
        cls._error_messages.update({
                'broker_fee': 'Broker Fee',
                })

    @classmethod
    def get_broker_fee_line_domain(cls, accounts, parties):
        return [
            ('account', 'in', accounts),
            ('party', 'in', parties),
            ('broker_fee_invoice_line', '=', None),
            ('journal.type', '!=', 'commission'),
            ['OR',
                [('origin.id', '!=', None, 'account.invoice')],
                [('origin.id', '!=', None, 'account.move')]
            ]]

    @classmethod
    def add_broker_fees_to_invoice(cls, invoices):
        pool = Pool()
        Line = pool.get('account.move.line')
        InvoiceLine = pool.get('account.invoice.line')
        Move = pool.get('account.move')
        Invoice = pool.get('account.invoice')

        invoices_updated = []
        selected = defaultdict(lambda: defaultdict(list))
        fees = cls.search([('broker_fee', '=', True)])
        accounts = []
        for fee in fees:
            account = fee.get_account_for_billing(None)
            if account:
                accounts.append(account.id)
        parties = [invoice.party.id for invoice in invoices]
        lines = Line.search(cls.get_broker_fee_line_domain(accounts, parties))
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
            selected[line.party][line.account].append(line)
        for invoice in invoices:
            if invoice.party not in selected:
                continue
            for account in selected[invoice.party]:
                fee_lines = selected[invoice.party][account]
                amount = sum(l.credit - l.debit for l in fee_lines)
                invoice_line = InvoiceLine()
                invoice_line.type = 'line'
                invoice_line.quantity = 1
                invoice_line.unit_price = amount
                invoice_line.account = account
                invoice_line.description = cls.raise_user_error(
                    'broker_fee', raise_exception=False)
                invoice_line.invoice = invoice
                invoice_line.save()
                Line.write(fee_lines, {
                        'broker_fee_invoice_line': invoice_line.id,
                        })
                invoices_updated.append(invoice)
        Invoice.update_taxes(invoices_updated)
        return invoices_updated
