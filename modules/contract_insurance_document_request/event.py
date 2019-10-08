# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

__all__ = [
    'EventLog',
    ]


class EventLog(metaclass=PoolMeta):
    __name__ = 'event.log'

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if (object_.__name__ == 'document.request.line'
                and model_name == 'party.party' and hasattr(object_.for_object,
                'party')):
            return [object_.for_object.party]
        return super(EventLog, cls).get_related_instances(object_, model_name)
