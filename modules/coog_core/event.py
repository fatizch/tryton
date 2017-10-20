# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool
from trytond.model import Model, Unique
from trytond.rpc import RPC
from trytond.cache import Cache

import model
import fields
import coog_string
import utils

__metaclass__ = PoolMeta
__all__ = [
    'Event',
    'EventType',
    'EventTypeAction',
    'ActionEventTypeRelation',
    ]


class Event(Model):
    'Event'

    __name__ = 'event'
    _event_type_cache = Cache('event_type')

    @classmethod
    def __setup__(cls):
        super(Event, cls).__setup__()
        cls.__rpc__.update({'ws_notify_events': RPC(readonly=False)})
        cls._error_messages.update({
                'missing_information': 'Some informations %s are missing to '
                'notify an event: %s',
                'error_object_found': 'Found no object or more than one object'
                ' with following information %s'})

    @classmethod
    def notify_events(cls, objects, event_code, description=None, **kwargs):
        'This method can be called each time an event happens'
        pool = Pool()
        EventTypeAction = pool.get('event.type.action')
        event_type_data = cls.get_event_type_data_from_code(event_code)
        actions = [EventTypeAction(**x) for x in event_type_data['actions']]
        if actions and objects:
            for action in actions:
                filtered = action.filter_objects(objects)
                if filtered:
                    action.execute(filtered, event_code, description,
                        **kwargs)

    @classmethod
    def get_event_type_data_from_code(cls, event_code):
        pool = Pool()
        EventType = pool.get('event.type')
        event_type_data = cls._event_type_cache.get(event_code,
            default=None)
        if not event_type_data:
            event_type, = EventType.search([('code', '=', event_code)])
            event_type_data = {'id': event_type.id,
                    'actions': [action.cache_data() for action in
                        event_type.actions]}
            cls._event_type_cache.set(event_code, event_type_data)
        return event_type_data

    @classmethod
    def ws_notify_events(cls, events):
        '''
            Web service to notify coog of an external event
            :param events: a structure like :
                [
                    object_: {
                        __name__: 'class_name',
                        _func_key: 'my_func_key
                        },
                    event_code: 'my_event_code',
                    description: 'description',
                    date: 'date'
                    }
                ]
        '''
        pool = Pool()
        for event in events:
            missing = [x for x in
                ['event_code', 'object_', 'date', 'description']
                if x not in event]
            if missing:
                cls.raise_user_error('missing_information', (missing,
                    str(event)))
            Object = pool.get(event['object_']['__name__'])
            found_objects = Object.search_for_export_import(event['object_'])
            if len(found_objects) == 1:
                cls.notify_events(found_objects, event['event_code'],
                    event['description'], date=event['date'],
                    external_event=True)
            else:
                cls.raise_user_error('error_object_found',
                    str(event['object_']))
        return {'return': True,
            'messages': 'All events treated'
            }


class EventType(model.CoogSQL, model.CoogView):
    'Event Type'

    __name__ = 'event.type'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)
    actions = fields.Many2Many('event.type.action-event.type', 'event_type',
        'action', 'Actions')

    @classmethod
    def __setup__(cls):
        super(EventType, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @classmethod
    def write(cls, *args):
        Pool().get('event')._event_type_cache.clear()
        super(EventType, cls).write(*args)

    @classmethod
    def _allow_update_links_on_xml_rec(cls):
        return True

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None, configuration=None):
        if not EventType.check_xml_record([self], None):
            skip_fields = set(self._fields.keys()) - {'actions'}
        return super(EventType, self).export_json(skip_fields,
            already_exported, output, main_object, configuration)

    @classmethod
    def delete(cls, instances):
        Pool().get('event')._event_type_cache.clear()
        super(EventType, cls).delete(instances)

    @classmethod
    def create(cls, vlist):
        Pool().get('event')._event_type_cache.clear()
        return super(EventType, cls).create(vlist)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)


class ActionEventTypeRelation(model.CoogSQL, model.CoogView):
    'Action Event Type Relation'

    __name__ = 'event.type.action-event.type'

    event_type = fields.Many2One('event.type', 'Event Type', required=True,
        ondelete='CASCADE', select=True)
    action = fields.Many2One('event.type.action', 'Action', ondelete='CASCADE',
        required=True)


class EventTypeAction(model.CoogSQL, model.CoogView):
    'Event Type Action'

    __name__ = 'event.type.action'
    _func_key = 'code'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    action = fields.Selection('get_action_types', 'Action', select=True)
    priority = fields.Integer('Priority', required=True)
    pyson_condition = fields.Char('Pyson Condition',
        states={'invisible': False}, help="A Pyson expression "
        "to filter the objects of the event. If not set, no filter will be "
        "applied. If the expression evaluates to True for an object, "
        "the action will be taken on it. Otherwise, it "
        "will be ignored. Example expression :\n Eval('status') == 'active'")
    handles_asynchronous = fields.Function(
        fields.Boolean('Handles asynchronous treatment', states={
            'invisible': True}),
        'on_change_with_handles_asynchronous')
    treatment_kind = fields.Selection([
            ('synchronous', 'Synchronous'),
            ('asynchronous', 'Asynchronous Batch'),
            ('asynchronous_queue', 'Immediate Asynchronous'),
            ], 'Treatment kind', states={
                'invisible': ~Eval('handles_asynchronous')})
    event_types = fields.Many2Many('event.type.action-event.type', 'action',
        'event_type', 'Event Types')
    show_descriptor = fields.Function(fields.Boolean('Show Descriptor',
            states={'invisible': True}), 'on_change_with_show_descriptor')
    descriptor = fields.Function(fields.Text('Descriptor',
            states={'invisible': ~Eval('show_descriptor')},
            depends=['show_descriptor']), 'on_change_with_descriptor')
    active = fields.Boolean('Active')

    @classmethod
    def __setup__(cls):
        super(EventTypeAction, cls).__setup__()
        cls._order.insert(0, ('priority', 'ASC'))
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @classmethod
    def _export_light(cls):
        return (super(EventTypeAction, cls)._export_light() |
            {'event_types'})

    @classmethod
    def write(cls, *args):
        Pool().get('event')._event_type_cache.clear()
        super(EventTypeAction, cls).write(*args)

    @classmethod
    def delete(cls, instances):
        Pool().get('event')._event_type_cache.clear()
        super(EventTypeAction, cls).delete(instances)

    @classmethod
    def create(cls, vlist):
        Pool().get('event')._event_type_cache.clear()
        return super(EventTypeAction, cls).create(vlist)

    @classmethod
    def default_treatment_kind(cls):
        return 'synchronous'

    @classmethod
    def default_active(cls):
        return True

    @fields.depends('action', 'treatment_kind', 'show_descriptor')
    def on_change_action(self):
        self.treatment_kind = 'synchronous'
        self.show_descriptor = len(self.on_change_with_descriptor()) > 0

    @classmethod
    def get_action_types(cls):
        return [('', '')]

    @classmethod
    def possible_asynchronous_actions(cls):
        return []

    @fields.depends('action')
    def on_change_with_handles_asynchronous(self, name=None):
        return self.action in self.possible_asynchronous_actions()

    def filter_objects(self, objects):
        if not self.pyson_condition:
            return objects
        return [x for x in objects if utils.pyson_result(
                self.pyson_condition, x) is True]

    def execute(self, objects, event_code, description=None, **kwargs):
        pass

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

    def on_change_with_descriptor(self, name=None):
        return ''

    @fields.depends('descriptor')
    def on_change_with_show_descriptor(self, name=None):
        return self.descriptor and len(self.descriptor) > 0

    def cache_data(self):
        return {'id': self.id, 'action': self.action}
