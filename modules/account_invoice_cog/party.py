from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    ]


class Party:
    __name__ = 'party.party'

    @classmethod
    def _export_light(cls):
        return (super(Party, cls)._export_light() |
            set(['supplier_payment_term', 'customer_payment_term']))
