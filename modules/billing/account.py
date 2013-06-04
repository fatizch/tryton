from trytond.pool import PoolMeta
from trytond.model import fields

__all__ = ['Move']
__metaclass__ = PoolMeta


class Move:
    __name__ = 'account.move'

    billing_period = fields.Many2One('billing.period', 'Billing Period',
        ondelete='RESTRICT')

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['contract.contract']
