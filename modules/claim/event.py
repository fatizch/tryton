
from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta
__all__ = [
    'EventLog',
    ]


class EventLog:

    __name__ = 'event.log'

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if (object_.__name__ == 'claim'
                and model_name == 'contract'):
            return [object_.get_contract()]
        return super(EventLog, cls).get_related_instances(
            cls, object_, model_name)
