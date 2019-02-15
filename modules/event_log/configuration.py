# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.cache import Cache
from trytond.pool import Pool
from trytond.modules.coog_core import coog_date, model, fields


__all__ = [
    'EventAggregateDescription',
    ]


class EventAggregateDescription(model.CoogSQL, model.CoogView):
    'Event Aggregate Description'

    __name__ = 'event.aggregate.description'

    duration = fields.Integer('Duration', required=True)
    unit = fields.Selection([('day', 'Day(s)'), ('month', 'Month(s)')],
        'Unit', required=True)
    event_type_aggregate = fields.Many2One('event.type',
        'Event Type To Aggregate', required=True, ondelete='RESTRICT',
        help='Event Type to aggregate for [duration] [unit]')
    event_type_notify = fields.Many2One('event.type',
        'Event Type To Notify', required=True, ondelete='RESTRICT',
        help='Event Type to notify when not aggregating')
    _get_description_event_code = Cache('get_description_event_code')
    _get_existing_event = Cache('get_existing_event')

    @classmethod
    def delete(cls, tables):
        cls._get_description_event_code.clear()
        cls._get_existing_event.clear()
        return super(EventAggregateDescription, cls).delete(tables)

    @classmethod
    def write(cls, *args):
        cls._get_description_event_code.clear()
        cls._get_existing_event.clear()
        return super(EventAggregateDescription, cls).write(*args)

    @classmethod
    def create(cls, vlist):
        cls._get_description_event_code.clear()
        cls._get_existing_event.clear()
        return super(EventAggregateDescription, cls).create(vlist)

    @classmethod
    def _build_domain(cls, obj, date, event_code):
        Description = Pool().get('event.aggregate.description')
        domain = ['AND',
            [('object_', '=', str(obj))],
            ['OR']]
        descriptions = Description.search([])
        for description in [x for x in descriptions
                if x.event_type_aggregate.code == event_code]:
            from_date = coog_date.add_duration(date, description.unit,
                -description.duration)
            domain[2].append([
                    ('date', '>=', from_date),
                    ('event_type.code', '=',
                        description.event_type_notify.code),
                    ])
        return domain

    @classmethod
    def get_eligible_codes(cls, obj, date, event_code):
        Description = Pool().get('event.aggregate.description')
        eligible_codes = cls._get_description_event_code.get(event_code,
            default=None)
        if eligible_codes is not None:
            return eligible_codes
        eligible_codes = list({x.event_type_notify.code
                for x in Description.search(
                    [('event_type_aggregate.code', '=', event_code)])
                })
        cls._get_description_event_code.set(event_code, eligible_codes)
        return eligible_codes

    @classmethod
    def get_existing_logs(cls, obj, date, event_code):
        EventLog = Pool().get('event.log')

        key = (event_code, date.strftime('%Y-%m-%d'))
        existing_logs = cls._get_existing_event.get(key, None)
        if existing_logs is not None:
            return existing_logs

        domain = cls._build_domain(obj, date, event_code)
        existing_logs = list({
                x.event_type.code for x in EventLog.search(domain)})

        cls._get_existing_event.set(key, existing_logs)
        return existing_logs

    @classmethod
    def check_for_notification(cls, obj, date, event_code):
        Description = Pool().get('event.aggregate.description')
        if not Description.search([], limit=1):
            return []
        if not isinstance(date, datetime.datetime):
            date = datetime.datetime.combine(
                date, datetime.datetime.min.time())
        eligible_codes = cls.get_eligible_codes(obj, date, event_code)
        existing_logs = cls.get_existing_logs(obj, date, event_code)
        return [x for x in eligible_codes if x not in existing_logs]
