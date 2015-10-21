from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields, export

__metaclass__ = PoolMeta

__all__ = [
    'Journal',
    ]


class Journal(export.ExportImportMixin):
    __name__ = 'account.statement.journal'
    _func_key = 'name'

    bank_deposit_ticket_statement = fields.Boolean(
        'Bank Deposit Ticket Statement')
    sequence = fields.Many2One('ir.sequence', 'Statement Sequence',
        required=True, domain=[('code', '=', 'statement')])

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls.validation.selection.append(('manual', 'Manual'))

    @classmethod
    def _export_light(cls):
        return super(Journal, cls)._export_light() | {'currency', 'company'}
