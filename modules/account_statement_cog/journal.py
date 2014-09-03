from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'Journal',
    ]


class Journal:
    __name__ = 'account.statement.journal'

    bank_deposit_ticket_statement = fields.Boolean(
        'Bank Deposit Ticket Statement')

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls.validation.selection.append(('manual', 'Manual'))
