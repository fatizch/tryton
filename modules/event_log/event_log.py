import datetime
from sql.conditionals import Coalesce

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
    _func_key = 'id'

    description = fields.Char('Description', readonly=True)
    description_str = fields.Function(
        fields.Char('Description'),
        'on_change_with_description_str')
    object_ = fields.Reference('Object', selection='models_get', readonly=True,
        required=True)
    date = fields.DateTime('Date', readonly=True, required=True)
    date_str = fields.Function(
        fields.Char('Date'),
        'on_change_with_date_str')
    user = fields.Many2One('res.user', 'User', readonly=True, required=True,
        ondelete='RESTRICT')
    event_type = fields.Many2One('event.type', 'Event Type', required=True,
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(EventLog, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    @fields.depends('date')
    def on_change_with_date_str(self, name=None):
        return Pool().get('ir.date').datetime_as_string(self.date)

    @fields.depends('description')
    def on_change_with_description_str(self, name=None):
        return self.description or self.object_.rec_name

    @staticmethod
    def order_date_str(tables):
        table, _ = tables[None]
        return [Coalesce(table.date, datetime.date.min)]

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
    def create_event_logs(cls, objects, event_type, description=None,
            **kwargs):
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

    @classmethod
    def search_for_export_import(cls, values):
        # importing an event log will always create a new one
        return []


class Event:
    __name__ = 'event'

    @classmethod
    def notify_events(cls, objects, event_code, description=None, **kwargs):
        pool = Pool()
        EventLog = pool.get('event.log')
        EventType = pool.get('event.type')
        event_type, = EventType.search([('code', '=', event_code)])
        EventLog.create_event_logs(objects, event_type,
            description, **kwargs)


class Trigger:
    __name__ = 'ir.trigger'

    event_type = fields.Many2One('event.type', 'Event Type')
