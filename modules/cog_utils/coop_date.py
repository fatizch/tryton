# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta


__all__ = [
    'HOURLY_DURATION',
    'DAILY_DURATION',
    'add_day',
    'add_month',
    'add_year',
    'add_duration',
    'get_end_of_period',
    'number_of_days_between',
    'number_of_years_between',
    'number_of_months_between',
    'duration_between',
    ]


HOURLY_DURATION = [
    ('second', 'Second'),
    ('minute', 'Minute'),
    ('hour', 'Hour'),
    ]

DAILY_DURATION = [
    ('', ''),
    ('day', 'Day'),
    ('week', 'Week'),
    ('month', 'Month'),
    ('quarter', 'Quarter'),
    ('half_year', 'Half-year'),
    ('year', 'Year'),
    ]

FREQUENCY = [
    ('', ''),
    ('dayly', 'Dayly'),
    ('weekly', 'Weekly'),
    ('monthly', 'Monthly'),
    ('quarterly', 'Quarterly'),
    ('half_yearly', 'Half-yearly'),
    ('yearly', 'Yearly'),
    ]


def add_day(date, nb):
    return date + relativedelta(days=nb)


def add_month(date, nb, stick_to_end_of_month=False):
    # If stick_to_end_of_month is True 28/02/2015 + 1 month = 31/03/2015
    next_month = date + relativedelta(months=nb)
    if not stick_to_end_of_month or date != get_end_of_month(date):
        return next_month
    return get_end_of_month(next_month)


def add_year(date, nb, stick_to_end_of_month=False):
    # If stick_to_end_of_month is True 28/02/2015 + 1 year = 29/02/2016
    next_year = date + relativedelta(years=nb)
    if not stick_to_end_of_month or date != get_end_of_month(date):
        return next_year
    return get_end_of_month(next_year)


def add_duration(date, duration_unit, duration=1, stick_to_end_of_month=False):
    '''
    Returns the first day of the begining of the next period
    for example : 01/01/Y + 1 year = 01/01/Y+1
    '''
    duration = int(duration)
    if duration_unit in ['day', 'dayly']:
        res = add_day(date, duration)
    elif duration_unit in ['week', 'weekly']:
        res = add_day(date, 7 * duration)
    elif duration_unit in ['month', 'monthly']:
        res = add_month(date, duration, stick_to_end_of_month)
    elif duration_unit in ['quarter', 'quarterly']:
        res = add_month(date, 3 * duration, stick_to_end_of_month)
    elif duration_unit in ['half_year', 'half_yearly']:
        res = add_month(date, 6 * duration, stick_to_end_of_month)
    elif duration_unit in ['year', 'yearly']:
        res = add_year(date, duration, stick_to_end_of_month)
    return res


def get_end_of_month(date):
    return date + relativedelta(day=31)


def get_begin_of_month(date):
    return datetime.date(date.year, date.month, 1)


def get_last_day_of_last_month(date):
    return add_day(get_begin_of_month(date), -1)


def get_end_of_period(date, duration_unit, duration=1):
    '''
    Returns the last day of period
    for example : 01/01/Y + 1 year = 31/12/Y
    '''
    res = add_duration(date, duration_unit, duration)
    return add_day(res, -1)


def number_of_days_between(start_date, end_date):
    return end_date.toordinal() - start_date.toordinal() + 1


def prorata_365(date1, date2):
    nb_days = (date2 - date1).days
    return nb_days / Decimal(365)


def number_of_years_between(date1, date2, prorata_method=None):
    if date1 > date2:
        return -number_of_years_between(date2, date1, prorata_method)
    date2 = add_day(date2, 1)
    nb_years = relativedelta(date2, date1).years
    if prorata_method is None:
        return nb_years
    try:
        new_date_1 = datetime.date(date1.year + nb_years, date1.month,
            date1.day)
    except ValueError:
        # Careful for leap years
        if date1.day == 29 and date1.month == 2:
            new_date_1 = datetime.date(date1.year + nb_years, date1.month,
                date1.day - 1)
        else:
            raise
    return nb_years + prorata_method(new_date_1, date2)


def number_of_months_between(date1, date2):
    date2 = add_day(date2, 1)
    delta = relativedelta(date2, date1)
    return delta.months + delta.years * 12


def duration_between(date1, date2, duration_unit):
    '''
    This function returns for
    date1=01/01/2013 date2=31/01/2013 -> 31 days, 1 Month
    date1=01/01/2013 date2=31/03/2013 -> 90 days, 3 months, 1 quarter
    date1=01/01/2013 date2=31/12/21013 -> 365 days, 12 months, 1 year
    '''
    if duration_unit == 'day':
        return number_of_days_between(date1, date2)
    elif duration_unit == 'week':
        return number_of_days_between(date1, date2) / 7
    elif duration_unit in ['month', 'quarter', 'half_year']:
        res = number_of_months_between(date1, date2)
        if duration_unit == 'quarter':
            return res / 3
        elif duration_unit == 'half_year':
            return res / 6
        else:
            return res
    elif duration_unit == 'year':
        return number_of_years_between(date1, date2)


def duration_between_and_is_it_exact(date1, date2, duration_unit):
    '''
    This function returns for
    date1=01/01/2013 date2=01/01/21014 -> (366 days, True), (12 months, False),
        (1 year, False)
    '''
    res = duration_between(date1, date2, duration_unit)
    end_date = get_end_of_period(date1, duration_unit, res)
    return res, end_date == date2


def convert_frequency(from_frequency, to_frequency):
    unsupported_freq = ['day', 'dayly', 'week', 'weekly']
    if from_frequency in unsupported_freq or to_frequency in unsupported_freq:
        raise Exception('Frequency Conversion Unsupported')

    def convert_frequency_to_month(freq):
        if freq in ['month', 'monthly']:
            return 1
        elif freq in ['quarter', 'quarterly']:
            return 3
        elif freq in ['half_year', 'half_yearly']:
            return 6
        elif freq in ['year', 'yearly']:
            return 12
    return (convert_frequency_to_month(to_frequency) /
        float(convert_frequency_to_month(from_frequency)))


def get_next_date_in_sync_with(date, day):
    if date:
        res = datetime.date(date.year, date.month, day)
    if res < date:
        res = add_month(res, 1)
    return res
