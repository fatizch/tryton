# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields, model, coog_date, utils

__all__ = [
    'EventTypeActionPlannedEventType',
    'EventTypeAction',
    ]


class EventTypeActionPlannedEventType(model.CoogSQL, model.CoogView):
    'Event Type Action Planned Event Type Relation'
    __name__ = 'event.type.action-planned_event.type'

    event_type = fields.Many2One('event.type', 'Event Type', required=True,
        ondelete='CASCADE', select=True)
    action = fields.Many2One('event.type.action', 'Action', ondelete='CASCADE',
        required=True)


class EventTypeAction:
    __metaclass__ = PoolMeta
    __name__ = 'event.type.action'

    delay = fields.Integer('Planned In',
        states={
            'invisible': Eval('action') != 'generate_planned_event',
            'required': Eval('action') == 'generate_planned_event',
            },
        depends=['action'], help='Planned gap after the event date')
    delay_unit = fields.Selection(coog_date.DAILY_DURATION, 'Unit',
        states={
            'invisible': Eval('action') != 'generate_planned_event',
            'required': Eval('action') == 'generate_planned_event',
            },
        depends=['action'])
    planned_event_types = fields.Many2Many(
        'event.type.action-planned_event.type',
        'action', 'event_type', 'Planned Event Types',
        states={
            'invisible': Eval('action') != 'generate_planned_event',
            'required': Eval('action') == 'generate_planned_event',
            },
        depends=['action'])

    @classmethod
    def __setup__(cls):
        super(EventTypeAction, cls).__setup__()
        cls._error_messages.update({
                'generate_planned_event': 'Generate Planned Event'
                })

    @classmethod
    def get_action_types(cls):
        return super(EventTypeAction, cls).get_action_types() + [
            ('generate_planned_event', cls.raise_user_error(
                'generate_planned_event', raise_exception=False))]

    def on_change_action(self):
        super(EventTypeAction, self).on_change_action()
        self.report_templates = []
        self.treatment_kind = 'synchronous'

    def execute(self, objects, event_code, description=None, **kwargs):
        if self.action != 'generate_planned_event':
            return super(EventTypeAction, self).execute(objects, event_code)
        PlannedEvent = Pool().get('planned.event')
        event_date = kwargs.get('event_date', utils.today())
        for planned_event_type in self.planned_event_types:
            PlannedEvent.create_planned_events(objects, planned_event_type.code,
                coog_date.add_duration(event_date, self.delay_unit,
                    self.delay), description=description)
