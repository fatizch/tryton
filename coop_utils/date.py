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


def add_days(date, nb):
    return date + datetime.timedelta(days=nb)


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
