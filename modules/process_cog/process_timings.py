# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, Button

from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta
__all__ = [
    'GetDatesForProcessTimings',
    'ProcessTimingSelectDates',
    'ProcessTimings',
    'ProcessTimingDisplayer',
    ]


class GetDatesForProcessTimings(Wizard):
    'Get Dates for Process Timings'

    __name__ = 'process.get_dates_for_timings'

    start_state = 'select_dates'
    select_dates = StateView('process.view_timings.select_dates',
        'process_cog.process_timings_select_dates_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'get_timings', 'tryton-go-next', default=True)])
    get_timings = StateAction('process_cog.act_view_timings')

    def do_get_timings(self, action):
        return action, {
            'extra_context': {
                'min_date': self.select_dates.start,
                'max_date': self.select_dates.end,
                }}


class ProcessTimingSelectDates(model.CoopView):
    'Process Timing Select Dates'

    __name__ = 'process.view_timings.select_dates'

    start = fields.DateTime('Start')
    end = fields.DateTime('End')


class ProcessTimings(Wizard):
    'Process Timings'

    __name__ = 'process.view_timings'

    start_state = 'timings'
    timings = StateView('process.view_timings.displayer',
        'process_cog.process_timings_displayer_view_form', [
            Button('Previous', 'select_dates', 'tryton-go-previous'),
            Button('Exit', 'end', 'tryton-cancel', default=True)])
    select_dates = StateAction('process_cog.act_get_dates_for_timings')

    def default_timings(self, name):
        return {
            'start': Transaction().context.get('min_date', None),
            'end': Transaction().context.get('max_date', None),
            'processes': [x.id for x in Pool().get('process').search([])],
            }


class ProcessTimingDisplayer(model.CoopView):
    'Process Timing Displayer'

    __name__ = 'process.view_timings.displayer'

    start = fields.DateTime('Start', readonly=True)
    end = fields.DateTime('End', readonly=True)
    processes = fields.One2Many('process', None, 'Processes',
        depends=['start', 'end'], readonly=True)
