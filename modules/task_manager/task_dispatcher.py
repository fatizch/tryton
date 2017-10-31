# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Window
from sql.aggregate import Min

from trytond.pyson import Eval, Bool, If
from trytond.wizard import Wizard, StateAction, StateTransition
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

from trytond.modules.coog_core import model, fields

__metaclass__ = PoolMeta

__all__ = [
    'ProcessLog',
    'TaskDispatcher',
    'LaunchTask',
    ]


class ProcessLog:
    __name__ = 'process.log'

    user_name = fields.Function(
        fields.Char('User'), 'get_user_name')
    task_start = fields.Function(
        fields.DateTime('Task Start'),
        'get_task_start')
    is_current_user = fields.Function(
        fields.Boolean('Is current user', depends=['user']),
        'get_is_current_user')
    task_start_date = fields.Function(
        fields.Date('Task Start'),
        'get_task_start_date')
    task_nb = fields.Function(
        fields.Integer('Task Number'),
        'get_task_nb')
    task_name = fields.Function(
        fields.Char('Name'),
        'get_task_name')
    teams = fields.Function(
        fields.Many2Many('res.team', None, None, 'Teams'),
        'get_teams')
    team_names = fields.Function(
        fields.Char('Teams'),
        'get_team_names', searcher='search_team_names')
    my_teams = fields.Function(
        fields.Boolean('My teams'),
        'get_my_teams', searcher='search_my_teams')
    is_authorized = fields.Function(
        fields.Boolean('Is Authorized'), 'get_is_authorized')

    @classmethod
    def view_attributes(cls):
        return super(ProcessLog, cls).view_attributes() + [
            ('/tree', 'colors', If(Bool(Eval('is_current_user')), 'blue',
                   If(Bool(~Eval('is_authorized')), 'grey', 'black')))
            ]

    @staticmethod
    def order_user_name(tables):
        table, _ = tables[None]
        return [table.user]

    def get_my_teams(self, name):
        if not self.from_state:
            return False
        return bool(set(self.teams) * set(self.from_state.teams))

    @classmethod
    def get_task_start(cls, logs, name):
        cursor = Transaction().connection.cursor()
        log = cls.__table__()
        tmp_query = log.select(log.id, log.task,
            Min(log.start_time, window=Window([log.task])).as_('min_start'),
            where=log.task.in_([str(x.task) for x in logs]))
        cursor.execute(*tmp_query.select(tmp_query.id, tmp_query.min_start,
                where=tmp_query.id.in_([x.id for x in logs])))
        values = {}
        for log_id, min_start in cursor.fetchall():
            values[log_id] = min_start
        return values

    def get_task_start_date(self, name):
        return self.task_start.date() if self.task_start else None

    def get_team_names(self, name):
        return ', '.join(x.name for x in self.teams)

    def get_teams(self, name):
        return [x.id for x in self.from_state.teams] if self.from_state else []

    def get_is_current_user(self, name):
        if not Transaction().user or not self.user:
            return False
        return Transaction().user == self.user.id

    def get_is_authorized(self, name):
        user = Transaction().user
        if not user or not self.from_state:
            return False
        for authorization in self.from_state.step.authorizations:
            if user in authorization.users:
                return True
        return False

    def get_task_nb(self, name):
        # used by graph presenter
        return 1

    def get_user_name(self, name=None):
        return self.user.rec_name if self.user else None

    def get_task_name(self, name=None):
        return self.task.task_name if self.task else None

    @classmethod
    def search_my_teams(cls, name, clause):
        if (clause[1] == '=' and clause[2]) or (
                clause[1] == '!=' and not clause[2]):
            op = 'in'
        else:
            op = 'not in'
        teams = Pool().get('res.user')(Transaction().user).teams
        possible_states = sum([[x.process_step for x in team.priorities]
                for team in teams], [])
        return [('from_state', op, possible_states)]

    @classmethod
    def search_team_names(cls, name, clause):
        Team = Pool().get('res.team')
        teams = Team.search([('rec_name', clause[1], clause[2])])
        possible_states = sum([[x.process_step for x in team.priorities]
                for team in teams], [])
        return [('from_state', 'in', possible_states)]


class TaskDispatcher(Wizard):
    'Task Dispatcher'

    __name__ = 'task.select'

    start_state = 'calculate_action'
    calculate_action = StateAction('process_cog.act_resume_process')

    @classmethod
    def __setup__(cls):
        super(TaskDispatcher, cls).__setup__()
        cls._error_messages.update({
                'no_task_selected': 'No task has been selected.',
                'no_task_found': 'No task found'
                })

    def do_calculate_action(self, action):
        User = Pool().get('res.user')
        user = User(Transaction().user)
        task = user.search_next_priority_task()
        if task:
            good_id = task.task.id
            good_model = task.task.__name__
        else:
            self.raise_user_error('no_task_selected')

        return (action, {
                'id': good_id,
                'model': good_model,
                'res_id': [good_id],
                'res_model': good_model,
                })


class LaunchTask(Wizard):
    'Launch Selected Task'

    __name__ = 'task.launch'

    start_state = 'find_action'
    find_action = StateTransition()
    view_task = model.VoidStateAction()
    resume_process_action = StateAction('process_cog.act_resume_process')

    @property
    def current_log(self):
        active_id = Transaction().context.get('active_id')
        active_model = Transaction().context.get('active_model')
        assert active_model == 'process.log'
        return Pool().get('process.log')(active_id)

    def transition_find_action(self):
        pool = Pool()
        config = pool.get('process.configuration').get_singleton()
        if config and config.share_tasks or (
                self.current_log.user.id in (Transaction().user, 0, 1)):
            # Users 0 is root (technical) and user 1 is admin. Those should not
            # interfere with the process
            return 'resume_process_action'
        return 'view_task'

    def do_view_task(self, action):
        pool = Pool()
        log = self.current_log
        Action = pool.get('ir.action')
        ActWindow = pool.get('ir.action.act_window')
        possible_actions = ActWindow.search([
                ('res_model', '=', log.task.__name__)])
        good_action = possible_actions[0]
        action = Action.get_action_values(
            'ir.action.act_window', [good_action.id])[0]

        views = action['views']
        if len(views) > 1:
            for view in views:
                if view[1] == 'form':
                    action['views'] = [view]
                    break
        return (action, {
                'id': log.task.id,
                'model': log.task.__name__,
                'res_id': [log.task.id],
                'res_model': log.task.__name__,
                })

    def do_resume_process_action(self, action):
        log = self.current_log

        return (action, {
                'id': log.task.id,
                'model': log.task.__name__,
                'res_id': [log.task.id],
                'res_model': log.task.__name__,
                })