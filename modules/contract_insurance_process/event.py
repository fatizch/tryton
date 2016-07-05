# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby

from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction:
    __name__ = 'event.type.action'

    @classmethod
    def get_action_types(cls):
        return super(EventTypeAction, cls).get_action_types() + [
            ('clear_process', 'Clear Process')]

    def execute(self, objects, event_code):
        pool = Pool()
        if self.action != 'clear_process':
            return super(EventTypeAction, self).execute(objects, event_code)

        def keyfunc(x):
            return x.__name__

        objects.sort(key=keyfunc)
        for name, group in groupby(objects, key=keyfunc):
            pool.get(name).write(list(group), {'current_state': None})

    def get_objects_for_process(self, objects, target_model_name):
        if target_model_name != 'contract':
            return super(EventTypeAction, self).get_objects_for_process(
                objects, target_model_name)
        process_objects = []
        for object_ in objects:
            process_objects.extend(self.get_contracts_from_object(object_))
        return process_objects
