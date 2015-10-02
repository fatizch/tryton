from trytond.pool import PoolMeta
from trytond.model import Model, Unique

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
    def notify_events(cls, objects, event_code, description=None, **kwargs):
        'This method can be called each time an event happens'
        pass


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
