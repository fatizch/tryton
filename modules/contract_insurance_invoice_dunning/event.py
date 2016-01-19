from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'EventLog',
    ]


class EventLog:
    __name__ = 'event.log'

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if object_.__name__ != 'account.dunning' or model_name != 'contract':
            return super(EventLog, cls).get_related_instances(object_,
                model_name)
        return [object_.contract]
