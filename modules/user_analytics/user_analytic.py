# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql import Literal
from sql.aggregate import Sum, Max, Min, Count
from sql.functions import Extract, Round

from trytond.pool import Pool
from trytond.config import config
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, model
from trytond.modules.report_engine import Printable


__all__ = [
    'UserConnection',
    'DailyConnection',
    'DailyGlobalConnection',
    'MonthlyGlobalConnection',
    ]


class UserConnection(model.CoogSQL, model.CoogView, Printable):
    'User Connection'
    __name__ = 'res.user.connection'

    user = fields.Function(fields.Many2One('res.user', 'User'), 'get_user')
    key = fields.Char('Key', select=True)
    date = fields.Date('Connection Date', select=True)
    last_activity = fields.Timestamp('Last Action Date')
    activity = fields.TimeDelta('Activity')
    terminated_reason = fields.Char('End Session Reason', select=True)
    inactivity = fields.TimeDelta('Inactivity')
    activity_str = fields.Function(fields.Char('Activity'),
        'get_timedelta_str')
    inactivity_str = fields.Function(fields.Char('Inactivity'),
        'get_timedelta_str')
    user_id = fields.Integer('User', required=True, select=True)

    @classmethod
    def __setup__(cls):
        super(UserConnection, cls).__setup__()
        cls._order = [
            ('date', 'ASC'),
            ('user_id', 'ASC'),
            ('create_date', 'ASC')
            ]

    @classmethod
    def set_end(cls, connections):
        cls.update_connections(connections)
        one_day = datetime.timedelta(days=1)
        timeout = datetime.timedelta(
            seconds=config.getint('session', 'timeout'))
        terminated = {x.key: "manual" if
            abs(datetime.datetime.now() - (x.last_activity or x.create_date)) <
                timeout else "timeout" for x in connections}
        out_connections = cls.search([
                ('key', 'in', [x.key for x in connections])])
        for connection in out_connections:
            connection.terminated_reason = terminated[connection.key]
            if connection in connections:
                last = connection.create_date
                # Need a datetime var because of bellow operation
                # Datetime - Datetime
                day_date_limit = datetime.datetime(year=last.year,
                    month=last.month, day=last.day) + one_day
                if terminated[connection.key] == "timeout":
                    last = connection.last_activity
                    if datetime.date.today() >= day_date_limit.date():
                        connection.inactivity += day_date_limit - last
                    else:
                        today = datetime.datetime.now()
                        connection.inactivity += today - last
        cls.save(out_connections)

    @classmethod
    def update_connections(cls, connections):
        now = datetime.datetime.now()
        today = now.date()
        time_off = datetime.datetime.combine(datetime.date.min,
            now.time()) - datetime.datetime.min
        timeout = datetime.timedelta(
            seconds=config.getint('session', 'timeout'))
        expired_connections = []
        for c in connections:
            timestamp = c.last_activity or c.create_date
            if abs(timestamp - now) > timeout:
                expired_connections.append(c)
                connections.remove(c)
        cls.create([{
                    'key': x.key, 'date': today,
                    'last_activity': x.last_activity, 'inactivity': time_off,
                    'user_id': x.user_id,
                    } for x in expired_connections if
                    x.create_date.date() != today])
        new_connections = Pool().get('res.user.connection').create([{
                    'key': x.key, 'date': today,
                    'last_activity': x.last_activity, 'user_id': x.user_id,
                    } for x in connections if x.create_date.date() != today])
        connections.extend(new_connections)
        cls.update_active(connections)
        for c in connections:
            if c.create_date.date() == today:
                c.last_activity = now
        cls.save(connections)

    @classmethod
    def update_active(cls, connections):
        Configuration = Pool().get('res.user.analytics.configuration')
        idletime = Configuration(1).inactivity_limit
        idletime = datetime.timedelta(seconds=idletime)
        today = datetime.date.today()
        now = datetime.datetime.now()
        one_day = datetime.timedelta(days=1)
        for con in connections:
            last = con.last_activity or con.create_date
            day_date_limit = datetime.datetime(year=last.year,
                month=last.month, day=last.day) + one_day
            timestamp = now - last
            if timestamp < idletime:
                if today >= day_date_limit.date():
                    if con.create_date.date() == today:
                        con.activity += now - datetime.datetime(
                            year=now.year, month=now.month, day=now.day)
                    else:
                        con.activity += day_date_limit - last
                else:
                    con.activity += timestamp
            else:
                if today >= day_date_limit.date():
                    if con.create_date.date() == today:
                        con.inactivity += now - datetime.datetime(
                            year=now.year, month=now.month, day=now.day)
                    else:
                        con.inactivity += day_date_limit - last
                else:
                    con.inactivity += timestamp

    def get_sender(self):
        company = Transaction().context.get('company')
        if company:
            return Pool().get('company.company')(company).party

    @classmethod
    def default_activity(cls):
        return datetime.timedelta(days=0)

    @classmethod
    def default_inactivity(cls):
        return datetime.timedelta(days=0)

    def get_user(self, name):
        return self.user_id

    def get_contact(self):
        company = Transaction().context.get('company')
        if company:
            return Pool().get('company.company')(company).party

    def get_timedelta_str(instance, name):
        if name == 'activity_str':
            return str(instance.activity).split('.', 2)[0]
        else:
            return str(instance.inactivity).split('.', 2)[0]


class DailyConnection(model.CoogSQL, model.CoogView):
    'Daily Connection'

    __name__ = 'res.user.connection.daily'

    date = fields.Date('Day')
    user = fields.Integer('User')
    user_res = fields.Function(fields.Many2One('res.user', 'User'), 'get_user')
    activity = fields.TimeDelta('Activity')
    activity_str = fields.Function(fields.Char('Average Activity'),
        'get_timedelta_str')
    inactivity = fields.TimeDelta('Inactivity')
    inactivity_str = fields.Function(fields.Char('Average Inactivity'),
        'get_timedelta_str')

    def get_timedelta_str(instance, name):
        if name == 'activity_str':
            return str(instance.activity).split('.', 2)[0]
        else:
            return str(instance.inactivity).split('.', 2)[0]

    def get_user(self, name):
        return self.user

    @staticmethod
    def table_query():
        user_connection = Pool().get('res.user.connection').__table__()
        user_id = user_connection.user_id
        activity = user_connection.activity
        inactivity = user_connection.inactivity
        date = user_connection.date
        return user_connection.select(
            Max(user_connection.id).as_('id'),
            Literal(0).as_('create_uid'),
            Literal(0).as_('create_date'),
            Literal(0).as_('write_uid'),
            Literal(0).as_('write_date'),
            date.as_('date'),
            user_id.as_('user'),
            Sum(activity).as_('activity'),
            Sum(inactivity).as_('inactivity'),
            group_by=[date, user_id])


class DailyGlobalConnection(DailyConnection):
    'Daily Global Connection'

    __name__ = 'res.user.connection.global.daily'

    activity_hours = fields.Function(fields.Numeric('Activity (h)', (4, 2)),
        'get_timedelta_hours')
    inactivity_hours = fields.Function(fields.Numeric('Inactivity (h)', (4, 2)),
        'get_timedelta_hours')

    def get_timedelta_hours(instance, name):
        if name == 'activity_hours':
            return instance.activity.total_seconds() / 3600
        else:
            return instance.inactivity.total_seconds() / 3600

    @classmethod
    def table_query(cls):
        sub = super(DailyGlobalConnection, cls).table_query()
        return sub.select(
            Max(sub.id).as_('id'),
            Literal(0).as_('create_uid'),
            Literal(0).as_('create_date'),
            Literal(0).as_('write_uid'),
            Literal(0).as_('write_date'),
            sub.date.as_('date'),
            Count(sub.user).as_('user'),
            (Sum(sub.activity) / Count(sub.user)).as_('activity'),
            (Sum(sub.inactivity) / Count(sub.user)).as_('inactivity'),
            group_by=[sub.date])


class MonthlyGlobalConnection(DailyGlobalConnection):
    'Monthly Global Connection'

    __name__ = 'res.user.connection.global.monthly'

    year = fields.Integer('Year')
    month = fields.Integer('Month')

    @classmethod
    def table_query(cls):
        sub = super(MonthlyGlobalConnection, cls).table_query()
        year = Extract('year', sub.date)
        month = Extract('month', sub.date)
        return sub.select(
            Max(sub.id).as_('id'),
            year.as_('year'),
            month.as_('month'),
            Literal(0).as_('create_uid'),
            Literal(0).as_('create_date'),
            Literal(0).as_('write_uid'),
            Literal(0).as_('write_date'),
            Min(sub.date).as_('date'),
            Round(Sum(sub.user) / Count(sub.id), 2).as_('user'),
            (Sum(sub.activity) / Count(sub.id)).as_('activity'),
            (Sum(sub.inactivity) / Count(sub.id)).as_('inactivity'),
            group_by=[year, month])
