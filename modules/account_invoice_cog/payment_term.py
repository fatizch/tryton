# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'PaymentTerm',
    'PaymentTermLine',
    'PaymentTermLineRelativeDelta',
    ]


class PaymentTerm:
    __name__ = 'account.invoice.payment_term'

    is_one_shot = fields.Function(
        fields.Boolean('One Shot'),
        'get_is_one_shot')

    def get_is_one_shot(self, name):
        return len(self.lines) == 1 and self.lines[0].type == 'remainder'


class PaymentTermLine:
    __name__ = 'account.invoice.payment_term.line'

    def get_date(self, date):
        for relativedelta_ in self.relativedeltas:
            date += relativedelta_.get_delta(date)
        return date


class PaymentTermLineRelativeDelta:
    __name__ = 'account.invoice.payment_term.line.delta'

    quarter = fields.Boolean('Quarter', help="Synchronise to calendar quarter "
        "-> march, june, september, december")

    def get_delta(self, date):
        delta = self.get()
        if not self.quarter:
            return delta
        delta.months = delta.months or 0
        delta.months += 3 - date.month % 3 if date.month % 3 else 0
        return delta
