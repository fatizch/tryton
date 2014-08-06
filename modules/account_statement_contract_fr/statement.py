from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

__metaclass__ = PoolMeta

__all__ = [
    'Line',
    ]


class Line:
    __name__ = 'account.statement.line'

    bank = fields.Many2One('bank', 'Bank',
        states={'invisible': ~Eval('in_bank_deposit_ticket')},
        depends=['in_bank_deposit_ticket'])
