from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.tools import grouped_slice
from trytond.model import ModelView, Workflow

from trytond.modules.cog_utils import fields

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
        super(MoveLine, cls).copy(lines, default)


class InvoiceLine:
    __name__ = 'account.invoice.line'

    principal_lines = fields.One2Many('account.move.line',
        'principal_invoice_line', 'Principal Lines', readonly=True,
        states={'invisible': ~Eval('principal_lines')})


class Invoice:
    __name__ = 'account.invoice'

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
