
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'EventLog',
    ]


class EventLog:

    __name__ = 'event.log'

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name == 'contract':
            if object_.__name__ == 'claim':
                return [object_.get_contract()]
            if object_.__name__ == 'claim.indemnification':
                return [object_.service.contract]
        return super(EventLog, cls).get_related_instances(object_, model_name)
