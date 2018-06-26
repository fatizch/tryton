# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'EventLog',
    'EventTypeAction',
    ]


class EventLog:
    __metaclass__ = PoolMeta
    __name__ = 'event.log'

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if object_.__name__ != 'account.dunning' or model_name != 'contract':
            return super(EventLog, cls).get_related_instances(object_,
                model_name)
        return [object_.contract]


class EventTypeAction:
    __metaclass__ = PoolMeta
    __name__ = 'event.type.action'

    def get_contracts_from_object(self, object_):
        contracts = super(EventTypeAction,
            self).get_contracts_from_object(object_)
        if object_.__name__ == 'account.dunning':
            contracts.append(object_.contract)
        return contracts
