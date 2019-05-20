# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__all__ = [
    'APIModel',
    ]


class APIModel(metaclass=PoolMeta):
    __name__ = 'api'

    @classmethod
    def update_transaction_context(cls, api_context):
        context = Transaction().context
        update = super().update_transaction_context(api_context)
        if 'company' in api_context:
            update['company'] = api_context.pop('company')
        elif 'company' not in context:
            user = Pool().get('res.user')(Transaction().user)
            if user.main_company:
                update['company'] = user.main_company.id
        return update
