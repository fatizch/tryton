# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction:
    __name__ = 'event.type.action'

    def get_objects_for_process(self, objects, target_model_name):
        if target_model_name != 'contract':
            return super(EventTypeAction, self).get_objects_for_process(
                objects, target_model_name)
        process_objects = []
        for object_ in objects:
            process_objects.extend(self.get_contracts_from_object(object_))
        return process_objects
