# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, And
from trytond.server_context import ServerContext
from trytond.modules.coog_core import fields

__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction:
    __metaclass__ = PoolMeta
    __name__ = 'event.type.action'

    @classmethod
    def __setup__(cls):
        super(EventTypeAction, cls).__setup__()
        cls.process_to_initiate.states['invisible'] = And(
            cls.process_to_initiate.states.get('invisible', True),
            Eval('action') != 'create_contract_notification')
        cls.process_to_initiate.depends.append('action')
        cls.filter_on_event_object.states['invisible'] = And(
            cls.filter_on_event_object.states.get('invisible', True),
            Eval('action') != 'create_contract_notification')
        cls.filter_on_event_object.depends.append('action')

    @fields.depends('filter_on_event_object')
    def on_change_with_show_descriptor(self, name=None):
        show = super(EventTypeAction, self).on_change_with_show_descriptor(name)
        return show and not self.filter_on_event_object

    def get_objects_for_process(self, objects, target_model_name):
        if target_model_name != 'contract':
            return super(EventTypeAction, self).get_objects_for_process(
                objects, target_model_name)
        process_objects = []
        for object_ in objects:
            process_objects.extend(self.get_contracts_from_object(object_))
        return process_objects

    def get_objects_to_filter(self, objects):
        if self.filter_on_event_object:
            return objects
        return super(EventTypeAction, self).get_objects_to_filter(objects)

    def create_contract_notification(self, contracts):
        notifications = super(EventTypeAction,
            self).create_contract_notification(contracts)
        if not self.process_to_initiate:
            return notifications
        state = self.step_to_start or self.process_to_initiate.first_step()
        with ServerContext().set_context(initiate_process=True):
            for notification in notifications:
                notification.current_state = state
        return notifications
