# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from dateutil import rrule
from dateutil.easter import easter

from trytond import backend
from trytond.pyson import Eval

from trytond.model import ModelView, ModelSQL, fields, Model
from trytond.pool import Pool


__all__ = [
    'Holiday',
    'Configuration',
    'BatchParamsConfig',
    ]


class Configuration(ModelSQL, ModelView):
    'Configuration'

    __name__ = 'work_days.configuration'

    holidays = fields.One2Many('work_days.holiday', 'configuration',
        'Holidays')
    code = fields.Char('Code', required=True, select=True)
    name = fields.Char('Name', required=True, translate=True)
    day = fields.Function(fields.Date('Day'), 'get_day', setter='setter_void')
    number_of_working_days = fields.Function(
        fields.Integer('Number Of Working Days'),
        'getter_void', setter='setter_void')
    shifted_day = fields.Function(fields.Date('Shifted Day'),
        'on_change_with_shifted_day')

    @classmethod
    def __setup__(cls):
        super(Configuration, cls).__setup__()
        cls._error_messages.update({
                'duplicate_holiday': 'Some holidays have duplicates',
                })

    @classmethod
    def validate(cls, configurations):
        super(Configuration, cls).validate(configurations)
        cls.check_duplicates(configurations)

    def getter_void(self, name):
        pass

    @classmethod
    def setter_void(cls, objects, name, values):
        pass

    def get_day(self, name):
        return datetime.date.today()

    @fields.depends('holidays', 'day')
    def on_change_day(self, name=None):
        year = self.day.year if self.day else None
        for holiday in self.holidays:
            holiday.holiday_date = holiday.calculate_date(year)

    @fields.depends('day', 'number_of_working_days', 'holidays')
    def on_change_with_shifted_day(self, name=None):
        return (self.add_workdays(self.day, self.number_of_working_days)
            if self.day and self.number_of_working_days else None)

    @staticmethod
    def is_duplicate_fixed(fixed_holidays):
        holidays_mon_day = [(x.month, x.day) for x in fixed_holidays]
        return len(set(holidays_mon_day)) != len(holidays_mon_day)

    @staticmethod
    def is_duplicate_easter_holiday(easter_holidays):
        holidays_easter = [x.easter_delta_days for x in easter_holidays]
        return len(set(holidays_easter)) != len(holidays_easter)

    @staticmethod
    def is_duplicate_weekly(weekly_holidays):
        holidays_weekly = [(x.weekly_day) for x in weekly_holidays]
        return len(set(holidays_weekly)) != len(holidays_weekly)

    @classmethod
    def check_duplicates(cls, configurations):
        for configuration in configurations:
            fixed_holidays = []
            easter_holidays = []
            weekly_holidays = []
            for holiday in configuration.holidays:
                if holiday.holiday_type == 'input':
                    fixed_holidays.append(holiday)
                elif holiday.holiday_type == 'weekly_day_off':
                    weekly_holidays.append(holiday)
                else:
                    easter_holidays.append(holiday)
            if (cls.is_duplicate_fixed(fixed_holidays)
                    or cls.is_duplicate_easter_holiday(easter_holidays)
                    or cls.is_duplicate_weekly(weekly_holidays)):
                configuration.raise_user_error('duplicate_holiday')

    def get_weekly_days_off(self):
        return [x.weekly_day for x in self.holidays
            if x.holiday_type == 'weekly_day_off']

    def get_fixed_holidays(self):
        return [(int(x.month), x.day) for x in self.holidays
            if x.holiday_type == 'input']

    def get_easter_holidays(self):
        return [x.easter_delta_days for x in self.holidays
            if x.holiday_type == 'easter_holiday']

    def add_workdays(self, start_date, nb_open_days):
        assert type(nb_open_days) == int and isinstance(start_date,
            (datetime.date, datetime.datetime))
        assert nb_open_days > 0
        if not start_date:
            return None
        weekly_days_off = self.get_weekly_days_off()
        fixed_holidays = self.get_fixed_holidays()
        easter_holidays = self.get_easter_holidays()
        rs = rrule.rruleset(cache=True)
        for day_off in weekly_days_off:
            rs.exrule(rrule.rrule(rrule.WEEKLY, dtstart=start_date,
                    byweekday=int(day_off)))
        for fixed_holiday in fixed_holidays:
            rs.exrule(rrule.rrule(rrule.YEARLY, dtstart=start_date,
                    bymonth=fixed_holiday[0], bymonthday=fixed_holiday[1]))
        for easter_holiday in easter_holidays:
            rs.exrule(rrule.rrule(rrule.YEARLY, dtstart=start_date,
                    byeaster=easter_holiday))
        it = 0
        date = start_date + datetime.timedelta(days=1)
        rs.rrule(rrule.rrule(rrule.DAILY, dtstart=date, count=1))
        count = rs.count()
        if count != 0:
            it += 1
        while it != nb_open_days:
            date += datetime.timedelta(days=1)
            rs.rrule(rrule.rrule(rrule.DAILY, dtstart=date, count=1))
            if rs.count() != count:
                it += 1
            count = rs.count()
        return date


class Holiday(ModelSQL, ModelView):
    'Holiday'
    __name__ = 'work_days.holiday'

    configuration = fields.Many2One('work_days.configuration', 'Configuration',
        required=True, ondelete='CASCADE', select=True)
    name = fields.Char('Name', states={
        'invisible': ~Eval('holiday_type').in_(['input', 'easter_holiday'])
        }, depends=['holiday_type'], translate=True)
    holiday_type = fields.Selection([
            ('input', 'Input'),
            ('weekly_day_off', 'Weekly Day Off'),
            ('easter_holiday', 'Easter Related Holiday'),
            ], 'Type', required=True, sort=False)
    easter_delta_days = fields.Integer('Delta days from Easter', states={
            'invisible': Eval('holiday_type') != 'easter_holiday',
            'required': Eval('holiday_type') == 'easter_holiday'
            }, depends=['holiday_type'])
    day = fields.Integer('Day', states={
            'invisible': Eval('holiday_type') != 'input',
            'required': Eval('holiday_type') == 'input'
            }, depends=['holiday_type'])
    month = fields.Selection([
            ('', ''),
            ('1', 'January'),
            ('2', 'February'),
            ('3', 'March'),
            ('4', 'April'),
            ('5', 'May'),
            ('6', 'June'),
            ('7', 'July'),
            ('8', 'August'),
            ('9', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December'),
            ], 'Month', sort=False, states={
            'invisible': Eval('holiday_type') != 'input',
            'required': Eval('holiday_type') == 'input'
            }, depends=['holiday_type'])
    weekly_day = fields.Selection([
            ('', ''),
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
            ], 'Weekly Day Off', sort=False, states={
            'invisible': Eval('holiday_type') != 'weekly_day_off',
            'required': Eval('holiday_type') == 'weekly_day_off'
            }, depends=['holiday_type'])
    holiday_date = fields.Function(
        fields.Date("Holiday's Date", states={
                'invisible': Eval('holiday_type') == 'weekly_day_off'},
            depends=['holiday_type']),
        'on_change_with_holiday_date')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        holiday_h = TableHandler(cls, module_name)
        has_holiday_date = holiday_h.column_exist('holiday_date')
        super(Holiday, cls).__register__(module_name)
        if has_holiday_date:
            holiday_h.drop_column('holiday_date')

    @classmethod
    def __setup__(cls):
        super(Holiday, cls).__setup__()
        cls._error_messages.update({
                'invalid_day_month': 'Invalid month/day combination',
                })

    @classmethod
    def validate(cls, holidays):
        super(Holiday, cls).validate(holidays)
        cls.check_day(holidays)

    @classmethod
    def check_day(cls, holidays):
        for holiday in holidays:
            if holiday.holiday_type == 'input':
                try:
                    datetime.date(1904, int(holiday.month), holiday.day)
                except ValueError:
                    holiday.raise_user_error('invalid_day_month')

    def on_change_holiday_type(self, name=None):
        self.day, self.month, self.easter_delta_days = None, None, None

    @fields.depends('configuration', 'holiday_type', 'easter_delta_days',
        'month', 'day')
    def on_change_with_holiday_date(self, name=None):
        if self.configuration and self.configuration.day:
            return self.calculate_date(self.configuration.day.year)

    def calculate_date(self, year):
        year = max(min(year, datetime.MAXYEAR), datetime.MINYEAR)
        if year is None or self.holiday_type == 'weekly_day_off':
            return None
        elif self.holiday_type == 'easter_holiday':
            return easter(year) + datetime.timedelta(
                days=self.easter_delta_days)
        else:
            return datetime.date(year, int(self.month), int(self.day))


class BatchParamsConfig(Model):
    'Batch Parameters Configuration'

    __name__ = 'batch.params_config'

    @classmethod
    def __setup__(cls):
        super(BatchParamsConfig, cls).__setup__()
        cls._error_messages.update({
                'no_conf': 'No configuration given',
                })

    @classmethod
    def get_computed_params(cls, params):
        c_params = super(BatchParamsConfig, cls).get_computed_params(params)
        if not c_params.get('working_days') or c_params.get('treatment_date'):
            return c_params
        conf_code = c_params.get('conf_code', None)
        if conf_code is None:
            cls.raise_user_error('no_conf')
        open_days = c_params.get('working_days', None)
        conn_date = c_params.get('connection_date', None)
        if type(conn_date) == str:
            start_date = datetime.datetime.strptime(conn_date, '%Y-%m-%d')
        else:
            start_date = conn_date
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        conf, = Configuration.search([('code', '=', conf_code)])
        treatment_date = conf.add_workdays(start_date, int(open_days))
        if isinstance(treatment_date, datetime.datetime):
            c_params['treatment_date'] = treatment_date.date()
        else:
            c_params['treatment_date'] = treatment_date
        c_params.pop('conf_code', None)
        c_params.pop('working_days', None)
        return c_params
