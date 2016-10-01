# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'PaymentTerm',
    ]


class PaymentTerm:
    __name__ = 'account.invoice.payment_term'

    is_one_shot = fields.Function(
        fields.Boolean('One Shot'),
        'get_is_one_shot')

    def get_is_one_shot(self, name):
        return len(self.lines) == 1 and self.lines[0].type == 'remainder'
