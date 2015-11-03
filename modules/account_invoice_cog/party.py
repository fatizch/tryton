from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'PartyInteraction',
    ]


class Party:
    __name__ = 'party.party'

    @classmethod
    def _export_light(cls):
        return (super(Party, cls)._export_light() |
            set(['supplier_payment_term', 'customer_payment_term']))


class PartyInteraction:
    __name__ = 'party.interaction'

    @classmethod
    def __setup__(cls):
        super(PartyInteraction, cls).__setup__()
        cls.for_object_ref.selection.append(['account.invoice', 'Invoice'])
