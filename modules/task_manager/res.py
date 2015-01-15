from trytond.pool import PoolMeta, Pool

from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, coop_string, model

__metaclass__ = PoolMeta

__all__ = [
    'User',
    'Priority',
    'Team',
    'TeamGroupRelation',
    'UserTeamRelation',
]


class User:
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
        cursor = Transaction().cursor
        Log = pool.get('process.log')
        log = Log.__table__()
        priority = pool.get('res.team.priority').__table__()

        if not self.teams:
            return None

        query_table = log.join(priority, condition=(
                priority.process_step == log.to_state))

        cursor.execute(*query_table.select(log.id,
            where=((priority.team.in_([team.id for team in self.teams]))
                & (log.latest == True) & (log.locked == False)),
            order_by=(priority.value, log.start_time),
            limit=1))

        ids = cursor.fetchone()
        if ids:
            return Log(ids[0])


class Priority(model.CoopSQL, model.CoopView):
    'Priority'

    __name__ = 'res.team.priority'

    process_step = fields.Many2One('process-process.step', 'Process Step',
        required=True, ondelete='CASCADE')
    team = fields.Many2One('res.team', 'Team', ondelete='CASCADE')
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


class TeamGroupRelation(model.CoopSQL):
    'Team - Group Relation'

    __name__ = 'res.team-res.group'

    team = fields.Many2One('res.team', 'Team', ondelete='CASCADE')
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE')


class Team(model.CoopSQL, model.CoopView):
    'Team'

    __name__ = 'res.team'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    users = fields.Many2Many('res.user-res.team', 'team', 'user', 'Users')
    users_links = fields.One2Many('res.user-res.team', 'team', 'Users')
    priorities = fields.One2Many('res.team.priority', 'team', 'Priorities',
        order=[('value', 'ASC')])
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
        result = super(Team, cls)._export_skips()
        result.add('users')
        return result

    @classmethod
    @model.CoopView.button_action('task_manager.wizard_add_user')
    def add_user_button(cls, teams):
        pass

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    def get_tasks_team(self, name):
        pool = Pool()
        cursor = Transaction().cursor
        Log = pool.get('process.log')
        log = Log.__table__()
        priority = pool.get('res.team.priority').__table__()

        query_table = log.join(priority, condition=(
                priority.process_step == log.to_state))

        cursor.execute(*query_table.select(log.id,
            where=((priority.team == self.id) & (log.latest == True)),
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
        cursor = Transaction().cursor
        Log = pool.get('process.log')
        log = Log.__table__()
        priority = pool.get('res.team.priority').__table__()

        query_table = log.join(priority, condition=(
                priority.process_step == log.to_state))

        cursor.execute(*query_table.select(log.id,
            where=((priority.team == self.id) & (log.latest == True)
                & (log.locked == False)),
            order_by=(priority.value, log.start_time),
            limit=1))

        ids = cursor.fetchone()
        if ids:
            return Log(ids[0])


class UserTeamRelation(model.CoopSQL, model.CoopView):
    'Relation between User and Team'

    __name__ = 'res.user-res.team'

    user = fields.Many2One('res.user', 'User')
    team = fields.Many2One('res.team', 'Team')
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
                ('to_state', 'in', steps),
                ('user', '=', self.id)])
