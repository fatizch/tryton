from trytond.pool import PoolMeta, Pool

from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, Button, StateTransition

from trytond.modules.coop_utils import model, fields


__all__ = [
    'User',
    'Session',
    'Priority',
    'Team',
    'TeamGroupRelation',
    'SelectUser',
    'AddTeamUser',
]


class User():
    'User'

    __metaclass__ = PoolMeta
    __name__ = 'res.user'

    team = fields.Many2One('task_manager.team', 'Team')


class Session():
    'Session'

    __metaclass__ = PoolMeta
    __name__ = 'ir.session'

    @classmethod
    def delete(cls, sessions):
        Log = Pool().get('coop_process.process_log')
        for session in sessions:
            locks = Log.search([
                ('user', '=', session.create_uid),
                ('locked', '=', True)])
            if locks:
                Log.write(locks, {'locked': False})
        super(Session, cls).delete(sessions)

    @classmethod
    def create(cls, values):
        cls.delete(cls.search([('create_uid', '=', Transaction().user)]))
        return super(Session, cls).create(values)


class Priority(model.CoopSQL, model.CoopView):
    'Priority'

    __name__ = 'task_manager.priority'

    process_step = fields.Many2One('process.process_step_relation',
        'Process Step', required=True, ondelete='CASCADE')
    team = fields.Many2One('task_manager.team', 'Team', ondelete='CASCADE')
    priority = fields.Integer('Priority')
    kind = fields.Selection(
        [
            ('user', 'User Issues'),
            ('non_user', 'Another User issues'),
            ('both', 'Both')],
        'Kind')

    def get_task(self, user):
        if not self.process_step:
            return None
        process = self.process_step.process
        good_act = process.get_act_window()
        Log = Pool().get('coop_process.process_log')
        domain = [
            ('latest', '=', True),
            ('to_state', '=', self.process_step),
            ('locked', '=', False)]
        if self.kind != 'both':
            domain.append(('user', '=' if self.kind == 'user' else '!=', user))
        res = Log.search(domain, limit=1)
        if not res:
            return None
        else:
            task = res[0].task
            return good_act, task.id, task.__name__

    @classmethod
    def default_kind(cls):
        return 'both'


class TeamGroupRelation(model.CoopSQL):
    'Team - Group Relation'

    __name__ = 'task_manager.team_group_relation'

    team = fields.Many2One('task_manager.team', 'Team', ondelete='CASCADE')
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE')


class Team(model.CoopSQL, model.CoopView):
    'Team'

    __name__ = 'task_manager.team'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    members = fields.One2Many(
        'res.user', 'team', 'Members', states={'readonly': True})
    authorizations = fields.Many2Many(
        'task_manager.team_group_relation', 'team', 'group', 'Authorizations')
    priorities = fields.One2Many(
        'task_manager.priority', 'team', 'Priorities',
        order=[('priority', 'ASC')],
    )

    @classmethod
    def __setup__(cls):
        super(Team, cls).__setup__()
        cls._buttons.update({
            'add_user_button': {}})

    @classmethod
    def _export_skips(cls):
        result = super(Team, cls)._export_skips()
        result.add('members')
        return result

    @classmethod
    @model.CoopView.button_action('task_manager.wizard_add_user')
    def add_user_button(cls, teams):
        pass

    def get_next_action(self, user):
        res = None
        for priority in self.priorities:
            res = priority.get_task(user)
            if res:
                break
        return res


class SelectUser(model.CoopView):
    'Select User'

    __name__ = 'task_manager.select_user'

    user = fields.Many2One('res.user', 'User')
    user_ok = fields.Function(
        fields.Char(
            'User Ok', on_change_with=['user']),
        'on_change_with_user_ok',
    )

    def on_change_with_user_ok(self):
        if not (hasattr(self, 'user') and self.user):
            return ''
        if self.user.team:
            return 'User is already a member of team %s' % (
                self.user.team.get_rec_name(None))
        return 'User does not have a team'


class AddTeamUser(Wizard):
    'Add Team User'

    __name__ = 'task_manager.add_user'

    start_state = 'select_user'
    select_user = StateView(
        'task_manager.select_user',
        'task_manager.select_user_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Add User', 'add_user', 'tryton-go-next'),
        ])
    add_user = StateTransition()

    def transition_add_user(self):
        the_team = Transaction().context.get('active_id')
        the_user = self.select_user.user
        the_user.team = the_team
        the_user.save()
        return 'end'
