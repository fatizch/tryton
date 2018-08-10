# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.modules.coog_core import model, fields, utils

__all__ = [
    'EventLog',
    'Trigger',
    'Event',
    ]


class EventLog(model.CoogSQL, model.CoogView):
    'Event Log'

    __name__ = 'event.log'
    _func_key = 'id'

    description = fields.Text('Description', readonly=True)
    description_str = fields.Function(
        fields.Char('Description'),
        'on_change_with_description_str')
    object_ = fields.Reference('Object', selection='models_get', readonly=True,
        required=True)
    date = fields.DateTime('Date', readonly=True, required=True)
    user = fields.Many2One('res.user', 'User', readonly=True, required=True,
        ondelete='RESTRICT')
    event_type = fields.Many2One('event.type', 'Event Type', required=True,
        ondelete='RESTRICT', readonly=True)
    icon = fields.Function(fields.Char('Icon'),
        'get_icon')
    in_user_filter = fields.Function(fields.Boolean('My events'),
        'get_in_user_filter', searcher='search_in_user_filter')

    @classmethod
    def __setup__(cls):
        super(EventLog, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    def get_icon(self, name):
        if self.event_type and self.event_type.icon:
            return self.event_type.icon_name

    @fields.depends('object_', 'description')
    def on_change_with_description_str(self, name=None):
        if self.description:
            return self.description.split('\n')[0]
        elif self.object_:
            if hasattr(self.object_, 'get_synthesis_rec_name'):
                return self.object_.get_synthesis_rec_name(name)
            else:
                return self.object_.rec_name
        else:
            return ''

    @staticmethod
    def models_get():
        return utils.models_get()

    @classmethod
    def create_event_logs(cls, objects, event_type_id, description=None,
            **kwargs):
        user_id = Transaction().user
        if 'date' in kwargs:
            date = kwargs['date']
        else:
            date = datetime.datetime.now()
        log_keys = cls.get_event_keys(objects)
        log_dicts = []
        for key in sum(log_keys.values(), []):
            key.update({
                    'date': date,
                    'user': user_id,
                    'event_type': event_type_id,
                    'description': description})
            log_dicts.append(key)
        return cls.create(log_dicts)

    @classmethod
    def create_event_logs_from_trigger(cls, objects, trigger):
        return cls.create_event_logs(objects, trigger.event_type.id,
            trigger.name)

    @classmethod
    def get_event_keys(cls, objects):
        return {object_: [{'object_': str(object_)}]
            for object_ in objects}

    @classmethod
    def get_related_instances(cls, object_, model_name):
        # Empty now, will be overriden for example in contract module to define
        # relations between objects
        return []

    @classmethod
    def add_func_key(cls, values):
        # importing an event log will always create a new one
        # override add_func_key since it's required during import
        values['_func_key'] = 0

    def get_in_user_filter(self, name):
        return False

    @classmethod
    def search_in_user_filter(cls, name, clause):
        assert clause[1] == '='
        user = Pool().get('res.user')(Transaction().user)
        if clause[2] is True:
            return ['OR',
                ('event_type.groups', '=', None),
                ('event_type.groups', 'in', [x.id for x in user.groups])]
        else:
            return []


class Event:
    __name__ = 'event'
    __metaclass__ = PoolMeta

    @classmethod
    def notify_events(cls, objects, event_code, description=None, **kwargs):
        super(Event, cls).notify_events(objects, event_code, description,
            **kwargs)
        if not objects:
            return
        pool = Pool()
        EventLog = pool.get('event.log')
        event_type_id = cls.get_event_type_data_from_code(event_code)['id']
        EventLog.create_event_logs(objects, event_type_id,
            description, **kwargs)


class Trigger:
    __name__ = 'ir.trigger'
    __metaclass__ = PoolMeta

    event_type = fields.Many2One('event.type', 'Event Type')
