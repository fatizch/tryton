# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'EventLog',
    ]


class EventLog:
    __metaclass__ = PoolMeta
    __name__ = 'event.log'

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name == 'claim' and object_.__name__ == 'underwriting':
            claims = set()
            if object_.on_object and object_.on_object.__name__ == 'claim':
                claims.add(object_.on_object)
            for elem in object_.results:
                if elem.claim:
                    claims.add(elem.claim)
            return list(claims)
        if (model_name == 'claim' and
                object_.__name__ == 'underwriting.result'):
            return cls.get_related_instances(object_.underwriting, model_name)
        return super(EventLog, cls).get_related_instances(object_, model_name)
