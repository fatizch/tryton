from trytond.pool import PoolMeta, Pool

from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, Button, StateTransition
from trytond.model import ModelSQL, ModelView, fields


__all__ = [
    'User',
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

    team = fields.Many2One(
        'task_manager.team',
        'Team',
    )


class Priority(ModelSQL, ModelView):
    'Priority'

    __name__ = 'task_manager.priority'

    process_step = fields.Many2One(
        'process.process_step_relation',
        'Process Step',
        required=True,
    )

    team = fields.Many2One(
        'task_manager.team',
        'Team',
        ondelete='CASCADE',
    )
    
    priority = fields.Integer('Priority', required=True)

    def get_task(self, user):
        if not self.process_step:
            return None

        process = self.process_step.process
        good_act = process.menu_item.action

        TargetModel = Pool().get(process.on_model.model)

        try:
            res, = TargetModel.search([
                    ('current_state', '=', self.process_step),
                ], limit=1)
            return good_act, res.id, res.__name__
        except ValueError:
            return None


class TeamGroupRelation(ModelSQL):
    'Team - Group Relation'

    __name__ = 'task_manager.team_group_relation'

    team = fields.Many2One(
        'task_manager.team',
        'Team',
        ondelete='CASCADE', 
    )

    group = fields.Many2One(
        'res.group',
        'Group',
        ondelete='CASCADE', 
    )


class Team(ModelSQL, ModelView):
    'Team'

    __name__ = 'task_manager.team'

    name = fields.Char(
        'Name',
        required=True,
    )

    code = fields.Char(
        'Code',
        required=True,
    )

    members = fields.One2Many(
        'res.user',
        'team',
        'Members',
        states={
            'readonly': True
        },
    )

    authorizations = fields.Many2Many(
        'task_manager.team_group_relation',
        'team',
        'group',
        'Authorizations',
    )

    priorities = fields.One2Many(
        'task_manager.priority',
        'team',
        'Priorities',
        order=[('priority', 'ASC')],
    )

    @classmethod
    def __setup__(cls):
        super(Team, cls).__setup__()
        cls._buttons.update({
            'add_user_button': {}})

    @classmethod
    @ModelView.button_action('task_manager.wizard_add_user')
    def add_user_button(cls, teams):
        pass

    def get_next_action(self, user):
        res = None
        for priority in self.priorities:
            res = priority.get_task(user)
            if res:
                break

        return res


class SelectUser(ModelView):
    'Select User'

    __name__ = 'task_manager.select_user'
    
    user = fields.Many2One(
        'res.user',
        'User',
    )

    user_ok = fields.Function(
        fields.Char(
            'User Ok',
            on_change_with=['user',],
        ),
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
            Button('Add User', 'add_user', 'tryton-go-next'),
            Button('Cancel', 'end', 'tryton-cancel'),
        ])

    add_user = StateTransition()

    def transition_add_user(self):
        the_team = Transaction().context.get('active_id')

        the_user = self.select_user.user

        the_user.team = the_team
        the_user.save()

        return 'end'
