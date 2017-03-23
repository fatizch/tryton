# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from collections import defaultdict

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond.modules.coog_core import model, fields, utils
from trytond.modules.rule_engine import get_rule_mixin

PROCESSED_STATES = {
    'readonly': Bool(Eval('processed'))
    }
DEPENDS = ['processed']


__all__ = [
    'EventPlanningConfigurationMixin',
    'PlannedEvent',
    ]


class EventPlanningConfigurationMixin(get_rule_mixin('planning_rule',
            'Planning Rule')):
    __metaclass__ = PoolMeta

    def calculate_planned_events(self, context_):
        return self.calculate_planning_rule(context_)

    @classmethod
    def sanitize_event_data(cls, events):
        Event = Pool().get('event')
        for event in events:
            event['event_type'] = Event.get_event_type_data_from_code(
                event['event'])['id']
            event.pop('event')

    @classmethod
    def event_exists(cls, existing_events, on_object, at_date, event_id,
            processed=True):
        return any(x.planned_date.date() == at_date and
            x.event_type.id == event_id and x.processed == processed
            for x in existing_events)

    def update_planned_events(self, context_, objects):
        PlannedEvent = Pool().get('planned.event')
        events = self.calculate_planned_events(context_)
        actions = {'save': [], 'delete': []}
        if not events:
            return actions
        self.sanitize_event_data(events)
        actions['delete'] = PlannedEvent.search([('on_object', 'in',
                    [str(x) for x in objects]),
                    ('processed', '=', False)])
        grouped_existing_events = defaultdict(list)
        existing_events = PlannedEvent.search([
                ('on_object', 'in', [str(o) for o in objects]),
                ('event_type', 'in', [x['event_type'] for x in events]),
                ])

        def group_func(x):
            return (x.on_object, x.event_type.id)
        existing_events = sorted(existing_events, key=group_func)
        for key, values in groupby(existing_events, group_func):
            grouped_existing_events[key] += values

        for event in events:
            for obj in objects:
                event['on_object'] = str(obj)
                key = (obj, event['event_type'])
                if (event['planned_date'] >= context_.get('date',
                            utils.today()) and not
                        self.event_exists(grouped_existing_events[key], obj,
                                event['planned_date'], event['event_type'])):
                    actions['save'].append(PlannedEvent(**event))
        return actions


class PlannedEvent(model.CoogSQL, model.CoogView):
    'Planned Event'
    __name__ = 'planned.event'

    description = fields.Text('Description', states=PROCESSED_STATES,
        depends=DEPENDS)
    on_object = fields.Reference('Object', selection='models_get',
        required=True, states=PROCESSED_STATES, depends=DEPENDS, select=True)
    planned_date = fields.Date('Planned Date', required=True,
        states=PROCESSED_STATES, depends=DEPENDS)
    event_type = fields.Many2One('event.type', 'Event Type', required=True,
        states=PROCESSED_STATES, depends=DEPENDS, ondelete='CASCADE')
    processed = fields.Boolean('Processed', readonly=True)

    @staticmethod
    def models_get():
        return utils.models_get()

    @staticmethod
    def default_processed():
        return False

    @classmethod
    def create_event_dict(cls, **kwargs):
        return {
            'description': kwargs.get('description'),
            'on_object': str(kwargs.get('on_object')),
            'planned_date': kwargs.get('planned_date'),
            'event_type': kwargs.get('event_type'),
            }

    @classmethod
    def create_planned_events(cls, objects, event_code, planned_date,
            description=None, **kwargs):
        event_type_id = Pool().get('event').get_event_type_data_from_code(
            event_code)['id']
        to_create = [cls.create_event_dict(
                description=description,
                object=x,
                planned_date=planned_date,
                event_type=event_type_id)
            for x in objects]
        if to_create:
            to_create = cls.create(to_create)
        return to_create

    @classmethod
    def process(cls, planned_events):
        def group_key(x):
            return (x.on_object.__name__, x.event_type)
        executed = []
        pool = Pool()
        PlannedEvent = pool.get('planned.event')
        Event = pool.get('event')
        planned_events = sorted(planned_events, key=group_key)
        processed_events = []
        for key, events in groupby(planned_events, group_key):
            events = list(events)
            event_type = key[1]
            objects = [x.on_object for x in events]
            Event.notify_events(objects, event_type.code)
            executed.extend(objects)
            processed_events.extend(events)
        if processed_events:
            PlannedEvent.write(processed_events, {'processed': True})
        return executed
