import datetime
from dateutil.relativedelta import relativedelta


__all__ = [
    'HOURLY_DURATION',
    'DAILY_DURATION',
    'add_day',
    'add_month',
    'add_year',
    'add_duration',
    'get_end_of_period',
    'convert_to_periods',
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


def add_day(date, nb):
    return date + relativedelta(days=nb)


def add_month(date, nb):
    return date + relativedelta(months=nb)


def add_year(date, nb):
    return date + relativedelta(years=nb)


def add_duration(date, duration, duration_unit):
    '''
    Returns the first day of the begining of the next period
    for example : 01/01/Y + 1 year = 01/01/Y+1
    '''
    if duration_unit == 'day':
        res = add_day(date, duration)
    elif duration_unit == 'week':
        res = add_day(date, 7 * duration)
    elif duration_unit == 'month':
        res = add_month(date, duration)
    elif duration_unit == 'quarter':
        res = add_month(date, 3 * duration)
    elif duration_unit == 'half_year':
        res = add_month(date, 6 * duration)
    elif duration_unit == 'year':
        res = add_year(date, duration)
    return res


def get_end_of_period(date, duration, duration_unit):
    '''
    Returns the last day of period
    for example : 01/01/Y + 1 year = 31/12/Y
    '''
    res = add_duration(date, duration, duration_unit)
    return add_day(res, -1)


def get_end_of_month(date):
    res = datetime.date(date.year, date.month, 1)
    res = add_month(res, 1)
    res = add_day(res, -1)
    return res


def convert_to_periods(dates):
    tmp_dates = dates
    tmp_dates.sort()
    res = []
    for i in range(0, len(tmp_dates) - 1):
        res.append(
            (tmp_dates[i], tmp_dates[i + 1] - datetime.timedelta(days=1)))
    res[-1][1] = res[-1][1] + datetime.timedelta(days=1)
    return res


def number_of_days_between(start_date, end_date):
    return end_date.toordinal() - start_date.toordinal() + 1


def number_of_years_between(date1, date2):
    return relativedelta(date2, date1).years


def number_of_months_between(date1, date2):
    return relativedelta(date1, date2).months + \
        relativedelta(date1, date2).years * 12


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

    date2 = add_day(date2, 1)
    if duration_unit == 'month':
        return number_of_months_between(date2, date1)
    elif duration_unit == 'quarter':
        return number_of_months_between(date2, date1) / 3
    elif duration_unit == 'half_year':
        return number_of_months_between(date2, date1) / 6
    elif duration_unit == 'year':
        return number_of_years_between(date2, date1)


def add_frequency(frequency, to_date):
    return add_duration(to_date, 1, frequency[:-2])
