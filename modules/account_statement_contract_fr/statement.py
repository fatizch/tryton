# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

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

    @classmethod
    def view_attributes(cls):
        return super(Statement, cls).view_attributes() + [(
                '/form/notebook/page[@id="statement_lines"]/'
                'group[@id="lines_without_bank"]',
                'states',
                {"invisible": Eval("in_bank_deposit_ticket", False)}
                ), (
                '/form/notebook/page[@id="statement_lines"]/'
                'group[@id="lines_with_bank"]',
                'states',
                {"invisible": ~Eval("in_bank_deposit_ticket", True)})
            ]

    def _get_grouped_line(self):
        Line = super(Statement, self)._get_grouped_line()

        class LineWithBank(Line):

            @property
            def bank(self):
                return self.lines[0].bank

        return LineWithBank
