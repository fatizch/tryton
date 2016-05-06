from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction:
    __name__ = 'event.type.action'

    def get_objects_for_process(self, objects, target_model_name):
        if target_model_name != 'claim':
            return super(EventTypeAction, self).get_objects_for_process(
                objects, target_model_name)
        process_objects = []
        for object_ in objects:
            process_objects.append(object_.service.claim)
        return process_objects
