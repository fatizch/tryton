from trytond.pool import PoolMeta, Pool
from trytond.model import Model, Unique
from trytond.rpc import RPC

import model
import fields
import coop_string

__metaclass__ = PoolMeta
__all__ = [
    'Event',
    'EventType',
    ]


class Event(Model):
    'Event'

    __name__ = 'event'

    @classmethod
    def __setup__(cls):
        super(Event, cls).__setup__()
        cls.__rpc__.update({'ws_notify_events': RPC(readonly=False)})
        cls._error_messages.update({
                'missing_information': 'Some informations %s are missing to '
                'notify an event: %s',
                'error_object_found': 'Found no object or more than one object '
                'with following information %s'})

    @classmethod
    def notify_events(cls, objects, event_code, description=None, **kwargs):
        'This method can be called each time an event happens'
        pass

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

    @classmethod
    def __setup__(cls):
        super(EventType, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)
