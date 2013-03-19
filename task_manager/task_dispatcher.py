import datetime

from trytond.wizard import Wizard, StateAction
from trytond.wizard import StateView, Button, StateTransition
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.coop_utils import utils, model, fields


__all__ = [
    'TaskDispatcher',
    'TaskDisplayer',
    'TaskSelector',
]


class TaskDisplayer(model.CoopView):
    'Task Displayer'

    __name__ = 'task_manager.task_displayer'

    task = fields.Many2One('process.process_step_relation', 'Task')
    nb_tasks = fields.Integer(
        'Number', on_change_with=['task'], depends=['task', 'kind'])
    kind = fields.Selection(
        [('team', 'Team'), ('process', 'Process')],
        'Kind', states={'invisible': True},
    )
    task_name = fields.Function(
        fields.Char('Task Name', on_change_with=['task'], depends=['task']),
        'on_change_with_task_name',
    )

    def on_change_with_task_name(self, name=None):
        if not (hasattr(self, 'task') and self.task):
            return ''
        return '%s - %s' % (
            self.task.process.fancy_name, self.task.step.fancy_name)

    def on_change_with_nb_tasks(self):
        if not (hasattr(self, 'task') and self.task):
            return None
        Log = Pool().get('coop_process.process_log')
        return Log.search_count([
            ('latest', '=', True),
            ('to_state', '=', self.task),
            ('locked', '=', False)])


class TaskSelector(model.CoopView):
    'Task Selector'

    __name__ = 'task_manager.task_selector'

    team = fields.Many2One(
        'task_manager.team', 'Team',
        on_change=['team', 'nb_tasks_team', 'nb_users_team', 'tasks_team'])
    process = fields.Many2One(
        'process.process_desc', 'Process',
        on_change=['process', 'nb_tasks_process', 'tasks_process'])
    nb_tasks_team = fields.Integer(
        'Team Tasks',
        states={'readonly': True})
    nb_users_team = fields.Integer(
        'Team Users',
        states={'readonly': True})
    nb_tasks_process = fields.Integer(
        'Process Tasks',
        states={'readonly': True})
    tasks_team = fields.One2ManyDomain(
        'task_manager.task_displayer', '', 'Team Tasks',
        domain=[('kind', '=', 'team')],
        states={'readonly': True},
    )
    tasks_process = fields.One2ManyDomain(
        'task_manager.task_displayer', '', 'Process Tasks',
        domain=[('kind', '=', 'process')],
        states={'readonly': True},
    )

    def on_change_team(self):
        if not (hasattr(self, 'team') and self.team):
            return {
                'nb_users_team': 0,
                'nb_tasks_team': 0,
                'tasks_team': []}
        result = {}
        User = Pool().get('res.user')
        result['nb_users_team'] = User.search_count([('team', '=', self.team)])
        tmp_result = {}
        final_result = []
        nb_tasks = 0
        TaskDisplayer = Pool().get('task_manager.task_displayer')
        for priority in self.team.priorities:
            if (priority.process_step.id, priority.priority) in tmp_result:
                continue
            task = TaskDisplayer()
            task.kind = 'team'
            task.task = priority.process_step
            task.task_name = '%s - %s' % (
                task.task.process.fancy_name, task.task.step.fancy_name)
            task.nb_tasks = task.on_change_with_nb_tasks()
            nb_tasks += task.nb_tasks
            tmp_result[(priority.process_step.id, priority.priority)] = task
            final_result.append(task)
        result['tasks_team'] = utils.WithAbstract.serialize_field(final_result)
        result['nb_tasks_team'] = nb_tasks
        return result

    def on_change_process(self):
        if not (hasattr(self, 'process') and self.process):
            return {
                'nb_tasks_process': 0,
                'tasks_process': []}
        result = {}
        tmp_result = []
        nb_tasks = 0
        TaskDisplayer = Pool().get('task_manager.task_displayer')
        for step in self.process.all_steps:
            task = TaskDisplayer()
            task.kind = 'process'
            task.task = step.id
            task.task_name = '%s - %s' % (
                task.task.process.fancy_name, task.task.step.fancy_name)
            task.nb_tasks = task.on_change_with_nb_tasks()
            nb_tasks += task.nb_tasks
            tmp_result.append(task)
        result['tasks_process'] = utils.WithAbstract.serialize_field(
            tmp_result)
        result['nb_tasks_process'] = nb_tasks
        return result

    def _on_change_with_tasks_team(self):
        if not (hasattr(self, 'team') and self.team):
            return []
        result = {}
        final_result = []
        TaskDisplayer = Pool().get('task_manager.task_displayer')
        for priority in self.team.priorities:
            if (priority.process_step.id, priority.priority) in result:
                continue
            task = TaskDisplayer()
            task.kind = 'team'
            task.task = priority.process_step
            task.task_name = '%s - %s' % (
                task.task.process.fancy_name, task.task.step.fancy_name)
            task.nb_tasks = task.on_change_with_nb_tasks()
            result[(priority.process_step.id, priority.priority)] = task
            final_result.append(task)
        return utils.WithAbstract.serialize_field(final_result)

    def _on_change_with_tasks_process(self):
        if not (hasattr(self, 'process') and self.process):
            return []
        result = []
        TaskDisplayer = Pool().get('task_manager.task_displayer')
        for step in self.process.all_steps:
            task = TaskDisplayer()
            task.kind = 'process'
            task.task = step.id
            task.nb_tasks = task.on_change_with_nb_tasks()
            result.append(task)
        return utils.WithAbstract.serialize_field(result)

    def _on_change_with_nb_users_team(self):
        if not (hasattr(self, 'team') and self.team):
            return None
        User = Pool().get('res.user')
        return User.search_count([('team', '=', self.team)])

    def _on_change_with_nb_tasks_team(self):
        if not (hasattr(self, 'tasks_team') and self.tasks_team):
            return None
        res = 0
        for task in self.tasks_team:
            res += task['nb_tasks']
        return res

    def _on_change_with_nb_tasks_process(self):
        if not (hasattr(self, 'tasks_process') and self.tasks_process):
            return None
        res = 0
        for task in self.tasks_process:
            res += task['nb_tasks']
        return res


class TaskDispatcher(Wizard):
    'Task Dispatcher'

    __name__ = 'task_manager.task_dispatcher'

    start_state = 'remove_locks'

    class LaunchStateAction(StateAction):
        '''
            We need a special StateAction in which we will override the
            get_action method to find what the user is supposed to do and
            dispatch it
        '''

        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            User = Pool().get('res.user')
            the_user = User(Transaction().user)

            if not (hasattr(the_user, 'team') and the_user.team):
                return None

            act = the_user.team.get_next_action(the_user)

            if not act:
                return None

            Action = Pool().get('ir.action')

            return Action.get_action_values(
                act[0].__name__,
                [act[0].id])[0], act[1], act[2]

    class VoidStateAction(StateAction):
        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            return None

    remove_locks = StateTransition()
    select_context = StateView(
        'task_manager.task_selector',
        'task_manager.task_selector_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Compute Task', 'calculate_action', 'tryton-ok'),
        ])
    calculate_action = VoidStateAction()

    @classmethod
    def __setup__(cls):
        super(TaskDispatcher, cls).__setup__()
        cls._error_messages.update({
            'no_task_available': 'There is no task available right now.',
        })

    def default_select_context(self, name):
        Selector = Pool().get('task_manager.task_selector')
        User = Pool().get('res.user')
        user = User(Transaction().user)
        if not (hasattr(user, 'team') and user.team):
            return {}
        selector = Selector()
        selector.team = user.team
        if not user.team.priorities:
            return {}
        good_priority = user.team.priorities[0]
        selector.process = good_priority.process_step.process
        changes = selector.on_change_team()
        changes.update(selector.on_change_process())
        for k, v in changes:
            setattr(selector, k, v)
        return utils.WithAbstract.serialize_field(selector)

    def transition_remove_locks(self):
        Log = Pool().get('coop_process.process_log')
        locked = Log.search([
            ('locked', '=', True),
            ('user', '=', Transaction().user)])
        if locked:
            Log.write(locked, {'locked': False})
        return 'select_context'

    def do_calculate_action(self, action):
        Log = Pool().get('coop_process.process_log')
        User = Pool().get('res.user')
        action = self.select_context.team.get_next_action(
            User(Transaction().user))
        if not action:
            self.raise_user_error('no_task_available')

        Action = Pool().get('ir.action')
        act, good_id, good_model = action
        act = Action.get_action_values(act.__name__, [act.id])[0]

        Session = Pool().get('ir.session')
        good_session, = Session.search(
            [('create_uid', '=', Transaction().user)])
        GoodModel = Pool().get(good_model)
        good_object = GoodModel(good_id)
        new_log = Log()
        new_log.user = Transaction().user
        new_log.locked = True
        new_log.task = utils.convert_ref_to_obj(good_object)
        new_log.from_state = good_object.current_state.id
        new_log.to_state = good_object.current_state.id
        new_log.start_time = datetime.datetime.now()
        new_log.session = good_session.key
        new_log.save()

        views = act['views']
        if len(views) > 1:
            for view in views:
                if view[1] == 'form':
                    act['views'] = [view]
                    break
        res = (
            act,
            {
                'id': good_id,
                'model': good_model,
                'res_id': good_id,
                'res_model': good_model,
            })
        return res
