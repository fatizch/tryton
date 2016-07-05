# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__metaclass__ = PoolMeta
__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    @property
    def dunning_procedure(self):
        if self.contract:
            return self.contract.product.dunning_procedure
        return super(MoveLine, self).dunning_procedure
