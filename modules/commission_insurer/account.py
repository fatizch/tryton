from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__all__ = ['MoveLine', 'InvoiceLine']
__metaclass__ = PoolMeta


class MoveLine:
    __name__ = 'account.move.line'
    principal_invoice_line = fields.Many2One('account.invoice.line',
        'Principal Invoice Line', readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._check_modify_exclude.add('principal_invoice_line')

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
