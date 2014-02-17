from trytond.pool import Pool

from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, Button, StateTransition

from trytond.modules.cog_utils import model, fields


__all__ = [
    'Priority',
    'Team',
    'TeamGroupRelation',
    'SelectUser',
    'AddTeamUser',
]


class Priority(model.CoopSQL, model.CoopView):
    'Priority'

    __name__ = 'res.team.priority'

    process_step = fields.Many2One('process-process.step', 'Process Step',
        required=True, ondelete='CASCADE')
    team = fields.Many2One('res.team', 'Team', ondelete='CASCADE')
    priority = fields.Integer('Priority')
    kind = fields.Selection([
            ('user', 'User Issues'),
            ('non_user', 'Another User issues'),
            ('both', 'Both')],
        'Kind')

    def get_task(self, user):
        if not self.process_step:
            return None
        process = self.process_step.process
        good_act = process.get_act_window()
        Log = Pool().get('process.log')
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

    __name__ = 'res.team-res.group'

    team = fields.Many2One('res.team', 'Team', ondelete='CASCADE')
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE')


class Team(model.CoopSQL, model.CoopView):
    'Team'

    __name__ = 'res.team'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    members = fields.One2Many('res.user', 'team', 'Members',
        states={'readonly': True})
    authorizations = fields.Many2Many('res.team-res.group', 'team', 'group',
        'Authorizations')
    priorities = fields.One2Many('res.team.priority', 'team', 'Priorities',
        order=[('priority', 'ASC')])

    @classmethod
    def __setup__(cls):
        super(Team, cls).__setup__()
        cls._buttons.update({
                'add_user_button': {},
                })

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

    __name__ = 'res.team.add_user.select'

    user = fields.Many2One('res.user', 'User')
    user_ok = fields.Function(
        fields.Char('User Ok'),
        'on_change_with_user_ok')

    @fields.depends('user')
    def on_change_with_user_ok(self):
        if not (hasattr(self, 'user') and self.user):
            return ''
        if self.user.team:
            return 'User is already a member of team %s' % (
                self.user.team.get_rec_name(None))
        return 'User does not have a team'


class AddTeamUser(Wizard):
    'Add Team User'

    __name__ = 'res.team.add_user'

    start_state = 'select_user'
    select_user = StateView('res.team.add_user.select',
        'task_manager.select_user_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Add User', 'add_user', 'tryton-go-next')])
    add_user = StateTransition()

    def transition_add_user(self):
        the_team = Transaction().context.get('active_id')
        the_user = self.select_user.user
        the_user.team = the_team
        the_user.save()
        return 'end'
