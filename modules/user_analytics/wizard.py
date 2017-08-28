# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import calendar

from trytond.pool import Pool
from trytond.wizard import StateAction, StateView, Button
from trytond.pyson import Eval, Bool, Not

from trytond.modules.coog_core import model, fields


__all__ = [
    'WizardConnection',
    'ConnectionDateSelector',
    ]


class WizardConnection(model.CoogWizard):
    'Wizard Connection'

    __name__ = 'res.user.connection.date_display'

    start = StateView(
        'res.user.connection.date_range',
        'user_analytics.user_connection_date_range', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate', 'generate', 'tryton-go-next', default=True)])
    generate = StateAction('report_engine.letter_generation_wizard')

    @classmethod
    def __setup__(cls):
        super(WizardConnection, cls).__setup__()
        cls._error_messages.update({
                'no_connections': 'Date range specified have no connections',
                })

    def do_generate(self, action):
        UserConnection = Pool().get('res.user.connection')
        view = self.start
        start_date = view.start_date or datetime.date.min
        end_date = view.end_date or datetime.date.max
        connections = UserConnection.search([
                ('date', '>=', start_date),
                ('date', '<=', end_date)],
            order=[('date', 'ASC'), ('user_id', 'ASC')])
        if not len(connections):
            self.raise_user_error('no_connection')
        return action, {'model': 'res.user.connection',
            'ids': [x.id for x in connections]}


class ConnectionDateSelector(model.CoogView):
    'Connection Date Range'

    __name__ = 'res.user.connection.date_range'

    preset_selector = fields.Selection('get_range', 'Set')
    start_date = fields.Date('Start date',
        states={'readonly': Not(Bool(Eval('preset_selector') == 'manual'))})
    end_date = fields.Date('End date',
        states={'readonly': Not(Bool(Eval('preset_selector') == 'manual'))})

    @classmethod
    def get_range(cls):
        return [
            ('current_month', 'Current Month'), ('past_month', 'Past Month'),
            ('current_year', 'Current Year'), ('past_year', 'Past Year'),
            ('manual', 'Manual')]

    @classmethod
    def default_preset_selector(cls):
        return cls.get_range()[0]

    @classmethod
    def default_end_date(cls):
        today = datetime.date.today()
        return today.replace(day=calendar.monthrange(today.year,
                today.month)[1])

    @classmethod
    def default_start_date(cls):
        day = datetime.date.today()
        return datetime.date(day.year, day.month, 1)

    @fields.depends('start_date', 'end_date', 'preset_selector')
    def on_change_preset_selector(self):
        day = datetime.timedelta(days=1)
        today = datetime.date.today()
        end_date = self.end_date
        start_date = self.start_date
        selection = self.preset_selector
        if selection == 'manual':
            return
        elif selection == 'current_month':
            end_date = datetime.date(today.year, (today.month + 1) % 13, 1)
            if today > end_date:
                end_date = datetime.date(end_date.year + 1, end_date.month,
                    1)
            end_date -= day
            start_date = datetime.date(end_date.year, end_date.month, 1)
        elif selection == 'past_month':
            end_date = datetime.date(today.year, today.month, 1) - day
            start_date = datetime.date(end_date.year, end_date.month, 1)
        elif selection == 'current_year':
            end_date = datetime.date(today.year + 1, 1, 1) - day
            start_date = datetime.date(end_date.year, 1, 1)
        else:
            end_date = datetime.date(today.year, 1, 1) - day
            start_date = datetime.date(end_date.year, 1, 1)
        self.start_date = start_date
        self.end_date = end_date

    @fields.depends('start_date', 'end_date')
    def on_change_start_date(self):
        if not self.end_date or not self.start_date:
            return
        if self.start_date > self.end_date:
            self.end_date = self.start_date + datetime.timedelta(days=1)

    @fields.depends('start_date', 'end_date')
    def on_change_end_date(self):
        if not self.start_date or not self.end_date:
            return
        if self.end_date < self.start_date:
            self.start_date = self.end_date - datetime.timedelta(days=1)
