# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool
from trytond.tools import grouped_slice
from trytond.model import ModelView, Workflow
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, utils

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
        table = TableHandler(cls, module)
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

    insurer_role = fields.Many2One('insurer', 'Insurer', ondelete='RESTRICT',
        readonly=True, states={
            'invisible': ~Eval('is_for_insurer'),
            'required': Bool(Eval('is_for_insurer')),
            }, depends=['is_for_insurer'])
    is_for_insurer = fields.Function(
        fields.Boolean('For insurer'), 'on_change_with_is_for_insurer')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        handler = TableHandler(cls, module_name)
        to_migrate = not handler.column_exist('insurer_role')

        super(Invoice, cls).__register__(module_name)

        # Migration from 1.10 : Store insurer
        if to_migrate:
            pool = Pool()
            to_update = cls.__table__()
            insurer = pool.get('insurer').__table__()
            party = pool.get('party.party').__table__()
            update_data = party.join(insurer, condition=(
                    insurer.party == party.id)
                ).select(insurer.id.as_('insurer_id'), party.id)
            cursor.execute(*to_update.update(
                    columns=[to_update.insurer_role],
                    values=[update_data.insurer_id],
                    from_=[update_data],
                    where=update_data.id == to_update.party))

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
        move_line = MoveLine.__table__()
        invoice_line = pool.get('account.invoice.line').__table__()

        super(Invoice, cls).cancel(invoices)

        # remove link to principal_invoice_line for move
        for sub_invoices in grouped_slice(invoices):
            ids = [i.id for i in sub_invoices]
            cursor = Transaction().connection.cursor()
            # in this case, a join would cost much more time
            invoice_line_query = invoice_line.select(invoice_line.id,
                where=(invoice_line.invoice.in_(ids)))
            cursor.execute(*invoice_line_query)
            invoice_line_ids = [x[0] for x in cursor.fetchall()]
            if not invoice_line_ids:
                return
            move_line_query = move_line.select(move_line.id, where=(
                    move_line.principal_invoice_line.in_(invoice_line_ids)))
            cursor.execute(*move_line_query)
            move_line_ids = [x[0] for x in cursor.fetchall()]
            if move_line_ids:
                move_lines = MoveLine.browse(move_line_ids)
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

    @fields.depends('party')
    def on_change_with_is_for_insurer(self, name=None):
        return self.party.is_insurer if self.party else False
