# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql import Null

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, coog_string, model

__all__ = [
    'User',
    'Priority',
    'Team',
    'TeamGroupRelation',
    'UserTeamRelation',
    'ProcessStepRelation',
    ]


class User:
    __metaclass__ = PoolMeta
    __name__ = 'res.user'

    teams = fields.Many2Many('res.user-res.team', 'user', 'team', 'Teams')
    nb_tasks = fields.Function(
        fields.Integer('Number of Tasks'),
        'get_nb_tasks')

    @classmethod
    def _export_light(cls):
        result = super(User, cls)._export_light()
        result.add('team')
        return result

    def get_nb_tasks(self, name):
        pool = Pool()
        Log = pool.get('process.log')
        return Log.search_count([
                ('latest', '=', True),
                ('user', '=', self.id)])

    def search_next_priority_task(self):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        Log = pool.get('process.log')
        log = Log.__table__()
        priority = pool.get('res.team.priority').__table__()

        if not self.teams:
            return None

        query_table = log.join(priority, condition=(
                priority.process_step == log.from_state))

        cursor.execute(*query_table.select(log.id,
            where=priority.team.in_([team.id for team in self.teams])
            & (log.end_time == Null)
            & (log.start_time <= datetime.datetime.now()),
            order_by=(priority.value, log.start_time),
            limit=1))

        ids = cursor.fetchone()
        if ids:
            return Log(ids[0])


class Priority(model.CoogSQL, model.CoogView):
    'Priority'

    __name__ = 'res.team.priority'

    process_step = fields.Many2One('process-process.step', 'Process Step',
        required=True, ondelete='CASCADE', select=True)
    team = fields.Many2One('res.team', 'Team', ondelete='CASCADE',
        required=True, select=True)
    value = fields.Integer('Value')
    nb_tasks = fields.Function(
        fields.Integer('Number of Tasks'),
        'get_nb_tasks')
    task_name = fields.Function(
        fields.Char('Task Name', depends=['process_step']),
        'on_change_with_task_name')

    def get_nb_tasks(self, name):
        pool = Pool()
        Log = pool.get('process.log')
        return Log.search_count([
            ('latest', '=', True),
            ('to_state', '=', self.process_step)
            ])

    @fields.depends('process_step')
    def on_change_with_task_name(self, name=None):
        if not self.process_step:
            return ''
        return '%s - %s' % (self.process_step.process.fancy_name,
            self.process_step.step.fancy_name)

    @classmethod
    def _export_light(cls):
        return super(Priority, cls)._export_light() | {'process_step'}


class TeamGroupRelation(model.CoogSQL):
    'Team - Group Relation'

    __name__ = 'res.team-res.group'

    team = fields.Many2One('res.team', 'Team', ondelete='CASCADE',
        required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
        required=True)


class Team(model.CoogSQL, model.CoogView):
    'Team'

    __name__ = 'res.team'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    users = fields.Many2Many('res.user-res.team', 'team', 'user', 'Users')
    users_links = fields.One2Many('res.user-res.team', 'team', 'Users',
        delete_missing=True)
    priorities = fields.One2Many('res.team.priority', 'team', 'Priorities',
        order=[('value', 'ASC')], delete_missing=True)
    tasks_team = fields.Function(
        fields.One2Many('process.log', None, 'Team Tasks',
            states={'readonly': True}),
        'get_tasks_team')
    nb_tasks = fields.Function(
        fields.Integer('Number of Tasks'),
        'get_nb_tasks')

    @classmethod
    def __setup__(cls):
        super(Team, cls).__setup__()
        cls._buttons.update({
                'add_user_button': {},
                })

    @classmethod
    def _export_skips(cls):
        return super(Team, cls)._export_skips() | {'users', 'users_links'}

    @classmethod
    @model.CoogView.button_action('task_manager.wizard_add_user')
    def add_user_button(cls, teams):
        pass

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

    def get_tasks_team(self, name):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        Log = pool.get('process.log')
        log = Log.__table__()
        priority = pool.get('res.team.priority').__table__()

        query_table = log.join(priority, condition=(
                priority.process_step == log.from_state))

        cursor.execute(*query_table.select(log.id,
            where=((priority.team == self.id) & (log.end_time == Null)),
            order_by=(priority.value, log.start_time)))
        return [x[0] for x in cursor.fetchall()]

    def get_nb_tasks(self, name):
        pool = Pool()
        Log = pool.get('process.log')
        valid_states = [priority.process_step.id
            for priority in self.priorities]
        return Log.search_count([
                ('latest', '=', True),
                ('to_state', 'in', valid_states)])

    def search_next_priority_task_for_team(self):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        Log = pool.get('process.log')
        log = Log.__table__()
        priority = pool.get('res.team.priority').__table__()

        query_table = log.join(priority, condition=(
                priority.process_step == log.to_state))

        cursor.execute(*query_table.select(log.id,
            where=(priority.team == self.id) & (log.end_time == Null),
            order_by=(priority.value, log.start_time),
            limit=1))

        ids = cursor.fetchone()
        if ids:
            return Log(ids[0])


class UserTeamRelation(model.CoogSQL, model.CoogView):
    'Relation between User and Team'

    __name__ = 'res.user-res.team'

    team = fields.Many2One('res.team', 'Team', ondelete='CASCADE',
        required=True, select=True)
    user = fields.Many2One('res.user', 'User', ondelete='RESTRICT',
        required=True)
    nb_tasks = fields.Function(
        fields.Integer('Number of Tasks'),
        'get_nb_tasks')

    def get_name(self, name):
        return self.user.rec_name

    def get_nb_tasks(self, name):
        pool = Pool()
        Log = pool.get('process.log')
        steps = [priority.process_step for priority in self.team.priorities]
        return Log.search_count([
                ('latest', '=', True),
                ('from_state', 'in', steps),
                ('user', '=', self.id)])


class ProcessStepRelation:
    __metaclass__ = PoolMeta
    __name__ = 'process-process.step'

    teams = fields.Many2Many('res.team.priority', 'process_step', 'team',
        'Teams')
