from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Line',
    'Statement',
    ]


class Line:
    __name__ = 'account.statement.line'

    bank = fields.Many2One('bank', 'Bank',
        states={'invisible': ~Eval('in_bank_deposit_ticket')},
        depends=['in_bank_deposit_ticket'])


class Statement:
    __name__ = 'account.statement'

    def _get_grouped_line(self):
        Line = super(Statement, self)._get_grouped_line()

        class LineWithBank(Line):

            @property
            def bank(self):
                return self.lines[0].bank

        return LineWithBank
