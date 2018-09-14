# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond import backend

from trytond.modules.coog_core import fields


__all__ = [
    'Insurer',
    ]


class Insurer:
    __metaclass__ = PoolMeta
    __name__ = 'insurer'

    group_insurer_invoices = fields.Boolean('Group Insurer Invoices',
        help='If True, all insurer related invoices (premiums / claims / etc) '
        'will be grouped in one')

    @classmethod
    def __register__(cls, module_name):
        super(Insurer, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        insurer_h = TableHandler(cls, module_name)
        # Migration from 1.10: Remove waiting_account on insurers
        if insurer_h.column_exist('waiting_account'):
            insurer_h.drop_column('waiting_account')

    @classmethod
    def get_insurers_waiting_accounts(cls, insurers, notice_kind):
        accounts_per_insurer = {}
        if notice_kind in ('options', 'all'):
            for insurer in insurers:
                billing_accounts = {x.account_for_billing
                    for x in insurer.options if x.account_for_billing}
                if billing_accounts:
                    accounts_per_insurer[insurer] = billing_accounts
        return accounts_per_insurer
