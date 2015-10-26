from trytond.pool import PoolMeta, Pool
from trytond.model import Model, Unique
from trytond.rpc import RPC
from trytond.cache import Cache

import model
import fields
import coop_string

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
        if actions:
            for action in actions:
                action.execute(objects)

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
            Objects is a structure like
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


class EventType(model.CoopSQL, model.CoopView):
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
    def delete(cls, instances):
        Pool().get('event')._event_type_cache.clear()
        super(EventType, cls).delete(*instances)

    @classmethod
    def create(cls, vlist):
        Pool().get('event')._event_type_cache.clear()
        return super(EventType, cls).create(vlist)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class ActionEventTypeRelation(model.CoopSQL, model.CoopView):
    'Action Event Type Relation'

    __name__ = 'event.type.action-event.type'

    event_type = fields.Many2One('event.type', 'Event Type', required=True,
        ondelete='CASCADE', select=True)
    action = fields.Many2One('event.type.action', 'Action', ondelete='CASCADE',
        required=True)


class EventTypeAction(model.CoopSQL, model.CoopView):
    'Event Type Action'

    __name__ = 'event.type.action'
    _func_key = 'code'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    action = fields.Selection('get_action_types', 'Action', select=True)
    priority = fields.Integer('Priority', required=True)

    @classmethod
    def write(cls, *args):
        Pool().get('event')._event_type_cache.clear()
        super(EventTypeAction, cls).write(*args)

    @classmethod
    def delete(cls, instances):
        Pool().get('event')._event_type_cache.clear()
        super(EventTypeAction, cls).delete(*instances)

    @classmethod
    def create(cls, vlist):
        Pool().get('event')._event_type_cache.clear()
        return super(EventTypeAction, cls).create(vlist)

    @classmethod
    def get_action_types(cls):
        return [('', '')]

    def execute(self, objects):
        pass

    @classmethod
    def __setup__(cls):
        super(EventTypeAction, cls).__setup__()
        cls._order.insert(0, ('priority', 'ASC'))
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    def cache_data(self):
        return {'id': self.id, 'action': self.action}
