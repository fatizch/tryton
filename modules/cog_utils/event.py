from trytond.pool import PoolMeta
from trytond.model import Model

import model
import fields

__metaclass__ = PoolMeta
__all__ = [
    'Event',
    'EventType',
    ]


class Event(Model):
    'Event'

    __name__ = 'event'

    @classmethod
    def notify_events(cls, objects, event_code, description=None):
        'This method can be called each time an event happens'
        pass


class EventType(model.CoopSQL, model.CoopView):
    'Event Type'

    __name__ = 'event.type'
    _func_key = 'code'

    @classmethod
    def __setup__(cls):
        super(EventType, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
            ]

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
