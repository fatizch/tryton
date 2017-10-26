# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Configuration',
    ]


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'

    surrender_journal = fields.Many2One('account.journal', 'Surrender Journal',
        help='The journal that will be used to pay surrendered contracts',
        ondelete='RESTRICT')
    surrender_payment_term = fields.Many2One('account.invoice.payment_term',
        'Surrender payment term', help='The payment term that will be used to '
        'pay surrendered contracts', ondelete='RESTRICT')
