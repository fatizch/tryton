# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class DsnMessage:
    __metaclass__ = PoolMeta
    __name__ = 'dsn.message'

    @classmethod
    def _get_origin(cls):
        res = super(DsnMessage, cls)._get_origin()
        return res + ['account.invoice']
