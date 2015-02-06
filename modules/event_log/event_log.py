import datetime

from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.modules.cog_utils import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'EventLog',
    'Trigger',
    'Event',
    ]


class EventLog(model.CoopSQL, model.CoopView):
    'Event Log'

    __name__ = 'event.log'

    description = fields.Char('Description', readonly=True)
    object_ = fields.Reference('Object', selection='models_get', readonly=True,
        required=True)
    date = fields.DateTime('Date', readonly=True, required=True)
    user = fields.Many2One('res.user', 'User', readonly=True, required=True,
        ondelete='RESTRICT')
    event_type = fields.Many2One('event.type', 'Event Type', required=True,
        ondelete='RESTRICT')

    @staticmethod
    def models_get():
        pool = Pool()
        Model = pool.get('ir.model')
        models = Model.search([])
        res = []
        for cur_model in models:
            res.append([cur_model.model, cur_model.name])
        return res

    @classmethod
    def create_event_logs(cls, objects, event_type, description=None):
        user_id = Transaction().user
        return cls.create([{
                    'date': datetime.datetime.now(),
                    'object_': '%s,%s' % (object_.__name__, object_.id),
                    'user': user_id,
                    'event_type': event_type,
                    'description': description}
                for object_ in objects])

    @classmethod
    def create_event_logs_from_trigger(cls, objects, trigger):
        return cls.create_event_logs(objects, trigger.event_type, trigger.name)


class Event:
    __name__ = 'event'

    @classmethod
    def notify_events(cls, objects, event_code, description=None):
        pool = Pool()
        EventLog = pool.get('event.log')
        EventType = pool.get('event.type')
        event_type, = EventType.search([('code', '=', event_code)])
        EventLog.create_event_logs(objects, event_type,
            description=description)


class Trigger:
    __name__ = 'ir.trigger'

    event_type = fields.Many2One('event.type', 'Event Type')
