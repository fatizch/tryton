# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond import backend


__all__ = [
    'Insurer',
    ]


class Insurer:
    __metaclass__ = PoolMeta
    __name__ = 'insurer'

    @classmethod
    def get_insurers_waiting_accounts(cls, insurers, notice_kind):
        if notice_kind == 'options':
            return list({(i, opt.account_for_billing) for i in insurers
                    for opt in i.options if opt.account_for_billing})

    @classmethod
    def __register__(cls, module_name):
        super(Insurer, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        insurer_h = TableHandler(cls, module_name)
        # Migration from 1.10: Remove waiting_account on insurers
        if insurer_h.column_exist('waiting_account'):
            insurer_h.drop_column('waiting_account')
