# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.server_context import ServerContext

__all__ = [
    'Payment',
    ]


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    @classmethod
    def fail_create_reject_fee(cls, *args):
        with ServerContext().set_context(default_maturity_date=True):
            super(Payment, cls).fail_create_reject_fee(*args)
