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
        return super(self, MoveLine).dunning_procedure()
