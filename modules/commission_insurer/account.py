from collections import defaultdict

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.tools import grouped_slice
from trytond.model import ModelView, Workflow

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'MoveLine',
    'InvoiceLine',
    'Invoice',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    principal_invoice_line = fields.Many2One('account.invoice.line',
        'Principal Invoice Line', readonly=True)

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._check_modify_exclude.add('principal_invoice_line')

    @classmethod
    def __register__(cls, module):
        super(MoveLine, cls).__register__(module)
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module)
        table.index_action('principal_invoice_line', 'remove')
        table.index_action(['principal_invoice_line', 'account'], 'add')

    @classmethod
    def copy(cls, lines, default=None):
        default = {} if default is None else default
        default.setdefault('principal_invoice_line', None)
        return super(MoveLine, cls).copy(lines, default)


class InvoiceLine:
    __name__ = 'account.invoice.line'

    principal_lines = fields.One2Many('account.move.line',
        'principal_invoice_line', 'Principal Lines', readonly=True,
        states={'invisible': ~Eval('principal_lines')})


class Invoice:
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._error_messages.update({
                'reset_commission_description':
                'Commission Reset following unreconciliation of invoice %s',
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, invoices):
        pool = Pool()
        MoveLine = pool.get('account.move.line')

        super(Invoice, cls).cancel(invoices)

        # remove link to principal_invoice_line for move
        for sub_invoices in grouped_slice(invoices):
            ids = [i.id for i in sub_invoices]
            move_lines = MoveLine.search([
                ('principal_invoice_line.invoice', 'in', ids)
                ])
            MoveLine.write(move_lines, {'principal_invoice_line': None})

    @classmethod
    def reset_commissions(cls, invoices):
        '''
            Resets commission insurer lines if necessary. If a line already has
            a principal_invoice_line set, it will create a new move with two
            opposite matching lines, so we can "move" the
            principal_invoice_line away from the line to pay. This will allow
            the line to pay to be once more included in an insurer invoice once
            the client invoice is paid again.
        '''
        super(Invoice, cls).reset_commissions(invoices)
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')

        lines_per_invoice = defaultdict(list)
        for invoice in invoices:
            for line in invoice.move.lines:
                if line.principal_invoice_line:
                    lines_per_invoice[invoice].append(line)
        if not lines_per_invoice:
            return
        moves = cls.create_reset_moves(lines_per_invoice)
        Move.save(moves)
        MoveLine.write(sum(lines_per_invoice.values(), []),
            {'principal_invoice_line': None})
        Move.post(moves)

    @classmethod
    def create_reset_moves(cls, lines_per_invoice):
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Journal = pool.get('account.journal')

        journal = Journal.search([('type', '=', 'commission_reset')])[-1]

        moves = []
        for invoice, line_group in lines_per_invoice.iteritems():
            description = cls.raise_user_error('reset_commission_description',
                (invoice.rec_name,), raise_exception=False)
            move = Move(journal=journal, company=line_group[0].move.company,
                date=utils.today(), origin=invoice, description=description)
            lines = []
            for line in line_group:
                same_line = MoveLine(party=line.party, account=line.account,
                    credit=line.credit, debit=line.debit,
                    principal_invoice_line=line.principal_invoice_line)
                other_line = MoveLine(party=line.party, account=line.account,
                    credit=line.debit, debit=line.credit)
                lines += [same_line, other_line]
            move.lines = lines
            moves.append(move)
        return moves
