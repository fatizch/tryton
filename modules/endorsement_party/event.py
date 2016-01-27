from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction:
    __name__ = 'event.type.action'

    def get_contracts_from_object(self, object_):
        contracts = super(EventTypeAction,
            self).get_contracts_from_object(object_)
        if object_.__name__ == 'endorsement':
            contracts.extend([x.contract for x
                    in object_.contract_endorsements])
            if object_.party_endorsements:
                for party_endorsement in object_.party_endorsements:
                    contracts.extend(
                        party_endorsement.party.get_all_contracts())
        return contracts
