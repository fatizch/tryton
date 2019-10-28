# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pyson import Eval
from trytond.pool import Pool
from trytond.model import Model, Unique
from trytond.model.exceptions import ValidationError
from trytond.rpc import RPC
from trytond.cache import Cache
from trytond.transaction import Transaction

from . import model
from . import fields
from . import coog_string
from . import utils

__all__ = [
    'Event',
    'EventType',
    'EventTypeAction',
    'ActionEventTypeRelation',
    'EventTypeGroupRelation',
    ]


class Event(Model):
    'Event'

    __name__ = 'event'
    _event_type_cache = Cache('event_type')

    @classmethod
    def __setup__(cls):
        super(Event, cls).__setup__()
        cls.__rpc__.update({'ws_notify_events': RPC(readonly=False)})

    @classmethod
    def __post_setup__(cls):
        super().__post_setup__()

        # We do not want to trigger events (which may call other systems, write
        # logs to the filesystem, etc...) when the transaction will be
        # rollbacked anyway
        #
        # We have to do this that way so that even if the method is overriden,
        # the check occurs before anything else is actually done
        old_notify = cls.notify_events

        def notify_events(*args, **kwargs):
            if Transaction().context.get('_will_be_rollbacked', False):
                return
            old_notify(*args, **kwargs)

        cls.notify_events = notify_events

    @classmethod
    @model.with_pre_commit_keyword_argument()
    def __execute_action(cls, action, filtered, event_code, description,
            **kwargs):
        # This method should never not be overriden.
        action.execute(filtered, event_code, description,
            **kwargs)

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
                    cls.__execute_action(action, filtered, event_code,
                        description, at_commit=action.at_commit, **kwargs)

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
                raise ValidationError(gettext(
                        'coog_core.msg_missing_information',
                        missing=', '.join(missing),
                        event=event,
                        ))
            Object = pool.get(event['object_']['__name__'])
            found_objects = Object.search_for_export_import(event['object_'])
            if len(found_objects) == 1:
                cls.notify_events(found_objects, event['event_code'],
                    event['description'], date=event['date'],
                    external_event=True)
            else:
                raise ValidationError(gettext(
                        'coog_core.msg_error_object_found',
                        object_=event['object_']))
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
    icon = fields.Many2One('ir.ui.icon', 'Icon', ondelete='RESTRICT')
    icon_name = fields.Function(
            fields.Char('Icon Name'),
            'get_icon_name')
    groups = fields.Many2Many(
        'event.type-res.group', 'event_type',
        'group', 'Groups', help='If the user belongs to one of the groups '
        'linked to the event type, he can see it by default in the event '
        'log.')

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
    def _export_skips(cls):
        return super()._export_skips() | {'actions'}

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

    def get_icon_name(self, name):
        if self.icon:
            return self.icon.name
        return ''


class ActionEventTypeRelation(model.CoogSQL, model.CoogView):
    'Action Event Type Relation'

    __name__ = 'event.type.action-event.type'

    event_type = fields.Many2One('event.type', 'Event Type', required=True,
        ondelete='CASCADE', select=True)
    action = fields.Many2One('event.type.action', 'Action', ondelete='CASCADE',
        required=True)
    active = fields.Function(fields.Boolean('Active'), 'get_active',
        searcher='search_active')

    def get_active(self, name):
        return self.action.active

    @classmethod
    def search_active(cls, name, clause):
        _, operator, operand = clause
        return [('action.active', operator, operand)]


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
    at_commit = fields.Boolean('At The Last Moment',
        help='If set, this ensure the action will be executed at the last '
        'moment and that everything has been executed correctly before '
        'processing this action. '
        'This could be usefull for report generation and avoid documents to '
        'be sent whereas something went wrong during processing.')

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

    @classmethod
    def default_at_commit(cls):
        return False

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


class EventTypeGroupRelation(model.CoogSQL, model.CoogView):
    'Event Type Group Relation'

    __name__ = 'event.type-res.group'

    event_type = fields.Many2One('event.type', 'Event Type',
        required=True, ondelete='CASCADE', select=True)
    group = fields.Many2One('res.group', 'Group',
        required=True, ondelete='CASCADE', select=True)
