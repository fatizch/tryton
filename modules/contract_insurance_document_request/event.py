# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'EventTypeAction',
    'EventLog',
    ]


class EventTypeAction(metaclass=PoolMeta):
    __name__ = 'event.type.action'

    def get_contracts_from_object(self, object_):
        contracts = super(EventTypeAction,
            self).get_contracts_from_object(object_)
        if object_.__name__ == 'document.request.line' and object_.contract:
            contracts.append(object_.contract)
        return contracts


class EventLog(metaclass=PoolMeta):
    __name__ = 'event.log'

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if (object_.__name__ == 'document.request.line'
                and model_name == 'party.party' and hasattr(object_.for_object,
                'party')):
            return [object_.for_object.party]
        return super(EventLog, cls).get_related_instances(object_, model_name)
