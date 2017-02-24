# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields


__all__ = [
    'Account',
    ]


class Account:
    __name__ = 'account.account'
    __metaclass__ = PoolMeta

    waiting_for_account = fields.Many2One(
        'account.account', 'Waiting Account For',
        ondelete='RESTRICT')
