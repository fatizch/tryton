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
        if (model_name == 'contract' and
                object_.__name__ == 'contract.covered_element'):
            return [object_.main_contract]
        return super(EventLog, cls).get_related_instances(object_,
            model_name)
