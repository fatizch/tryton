# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = [
    'Contract',
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    def create_request_hash(self):
        pool = Pool()
        Token = pool.get('api.token')
        Token.create_request_hash(self.parties)

    def after_activate(self):
        super(Contract, self).after_activate()
        self.create_request_hash()
