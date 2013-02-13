import datetime
from dateutil.relativedelta import relativedelta

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
    return date + relativedelta(year=nb)


def add_duration(date, duration, duration_unit):
    if duration_unit == 'day':
        return add_day(date, duration - 1)
    elif duration_unit == 'week':
        return add_day(date, 7 * duration)
    elif duration_unit == 'month':
        return add_month(date, duration)
    elif duration_unit == 'quarter':
        return add_month(date, 3 * duration)
    elif duration_unit == 'half_year':
        return add_month(date, 6 * duration)
    elif duration_unit == 'year':
        return add_year(date, duration)


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
    return relativedelta(date1, date2).months


def duration_between(date1, date2, duration_unit):
    if duration_unit == 'day':
        return number_of_days_between(date1, date2)
    elif duration_unit == 'week':
        return number_of_days_between(date1, date2) / 7
    elif duration_unit == 'month':
        return number_of_months_between(date2, date1)
    elif duration_unit == 'quarter':
        return number_of_months_between(date2, date1) / 3
    elif duration_unit == 'half_year':
        return number_of_months_between(date2, date1) / 6
    elif duration_unit == 'year':
        return number_of_years_between(date2, date1)
