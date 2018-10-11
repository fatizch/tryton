# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from sql import Null

from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, Workflow
from trytond.transaction import Transaction
from trytond.tools import grouped_slice

from trytond.modules.coog_core import fields, utils

__all__ = [
    'MoveLine',
    'Invoice',
    ]


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    principal_invoice_line = fields.Many2One('account.invoice.line',
        'Principal Invoice Line', readonly=True, ondelete='SET NULL')

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._check_modify_exclude.add('principal_invoice_line')

    @classmethod
    def copy(cls, lines, default=None):
        default = {} if default is None else default
        default.setdefault('principal_invoice_line', None)
        return super(MoveLine, cls).copy(lines, default)


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._error_messages.update({
                'reset_principal_line_description': 'Principal line reset '
                'following unreconciliation of invoice %s'
                })
        cls.business_kind.selection.append(('slip', 'Slip'))

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, invoices):
        super(Invoice, cls).cancel(invoices)
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        move_line = MoveLine.__table__()
        to_update = MoveLine.__table__()
        invoice_line = pool.get('account.invoice.line').__table__()

        # Clear the principal line field of move lines linked to the lines of
        # the cancelled invoices
        cursor = Transaction().connection.cursor()
        for sub_invoices in grouped_slice(invoices):
            invoices_ids = [i.id for i in sub_invoices]
            query_table = invoice_line.join(move_line,
                condition=move_line.principal_invoice_line == invoice_line.id
                ).select(move_line.id,
                where=invoice_line.invoice.in_(invoices_ids))
            cursor.execute(*to_update.update(
                    [to_update.principal_invoice_line], [Null],
                    from_=[query_table],
                    where=query_table.id == to_update.id))

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        paid_invoices = [i for i in invoices if i.state == 'paid']

        super(Invoice, cls).post(invoices)

        if paid_invoices:
            cls.reset_principal_lines(paid_invoices)

    @classmethod
    def reset_principal_lines(cls, invoices):
        '''
            Resets the move lines of the invoices which were already linked to
            a principal line.

            If a line already has a principal_invoice_line set, it will create
            a new move with two opposite matching lines, so we can "move" the
            principal_invoice_line away from the line to pay.

            This will allow the line to pay to be once more included in a slip
            once the client invoice is paid again.
        '''
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

        reset_moves = cls.create_reset_moves(lines_per_invoice)
        Move.save(reset_moves)
        Move.post(reset_moves)

        move_line_ids = [x.id for x in sum(lines_per_invoice.values(), [])]
        if move_line_ids:
            cursor = Transaction().connection.cursor()
            move_line = MoveLine.__table__()
            cursor.execute(*move_line.update(
                    [move_line.principal_invoice_line],
                    [Null], where=move_line.id.in_(move_line_ids)))

    @classmethod
    def create_reset_moves(cls, lines_per_invoice):
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Journal = pool.get('account.journal')

        journal, = Journal.search([('type', '=', 'principal_line_reset')])

        moves = []
        for invoice, line_group in lines_per_invoice.iteritems():
            description = cls.raise_user_error(
                'reset_principal_line_description', (invoice.rec_name,),
                raise_exception=False)
            move = Move(journal=journal, company=line_group[0].move.company,
                date=utils.today(), origin=invoice, description=description)
            lines = []
            for line in line_group:
                copied_line = MoveLine(party=line.party, account=line.account,
                    credit=line.credit, debit=line.debit,
                    principal_invoice_line=line.principal_invoice_line)
                inverted_line = MoveLine(party=line.party, account=line.account,
                    credit=line.debit, debit=line.credit)
                lines += [copied_line, inverted_line]
            move.lines = lines
            moves.append(move)
        return moves
