from trytond.pool import PoolMeta

__all__ = [
    'EventLog',
    'EventTypeAction',
    ]


class EventTypeAction:
    __metaclass__ = PoolMeta
    __name__ = 'event.type.action'

    def get_contract_sets_from_object(self, object_):
        if object_.__name__ != 'endorsement.set':
            return self.get_contract_sets_from_object(object_)
        return [object_.contract_set]


class EventLog:
    __metaclass__ = PoolMeta
    __name__ = 'event.log'

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if (model_name == 'contract.set' and
                object_.__name__ == 'endorsement.set'):
            return [object_.contract_set]
        return super(EventLog, cls).get_related_instances(object_, model_name)
