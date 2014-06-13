import datetime

from trytond.wizard import Wizard, StateAction
from trytond.wizard import StateView, Button, StateTransition
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

from trytond.modules.cog_utils import utils, model, fields

__metaclass__ = PoolMeta

__all__ = [
    'ProcessLog',
    'TaskDispatcher',
    'TaskDisplayer',
    'TaskSelector',
    'LaunchTask',
    ]


class ProcessLog:
    __name__ = 'process.log'

    priority = fields.Function(fields.Integer('Priority'), 'get_priority')
    task_start = fields.Function(
        fields.DateTime('Task Start'),
        'on_change_with_task_start')
    task_selected = fields.Function(
        fields.Boolean('Selected'),
        'get_task_selected', setter='setter_void')
    is_current_user = fields.Function(
        fields.Boolean('Is current user', depends=['user']),
        'get_is_current_user')

    @classmethod
    def order_priority(cls, tables):
        process_log, _ = tables[None]
        return [process_log.id]

    @classmethod
    def setter_void(cls, *args):
        pass

    def get_priority(self, name):
        team = utils.get_team()
        if not team:
            return None
        for priority in team.priorities:
            if priority.process_step.id == self.to_state.id:
                return priority.priority
        return None

    def get_task_selected(self, name):
        return False

    @fields.depends('task')
    def on_change_with_task_start(self, name=None):
        if not (hasattr(self, 'task') and self.task):
            return None
        start_log, = self.search([
            ('from_state', '=', None),
            ('task', '=', utils.convert_to_reference(self.task))], limit=1)
        return start_log.start_time

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        result = super(ProcessLog, cls).search(domain, offset, limit, order,
            count, query)
        if not (order and len(order) == 1):
            return result
        if not order[0][0] in ('priority', 'task_start'):
            return result
        elif order[0][0] == 'priority':
            team = utils.get_team()
            if not team:
                return result
            ordering_table = {}
            count = 0
            for priority in team.priorities:
                if priority.process_step.id in ordering_table:
                    continue
                ordering_table[priority.process_step.id] = count
                count += 1

            def order_priority(x):
                try:
                    result = ordering_table[x.to_state.id]
                    if x.user.id == Transaction().user:
                        return result - 0.5
                    return result
                except KeyError:
                    return len(ordering_table) + 1

            order_func = order_priority
        elif order[0][0] == 'task_start':
            def order_start_task(x):
                return x.task_start if hasattr(x, 'task_start') else None

            order_func = order_start_task

        if order[0][1] == 'ASC':
            return sorted(result, key=order_func)
        else:
            return sorted(result, key=order_func, reverse=True)

    def get_is_current_user(self, name):
        if not Transaction().user:
            return False
        return Transaction().user == self.user.id


class TaskDisplayer(model.CoopView):
    'Task Displayer'

    __name__ = 'task.select.available_tasks.task'

    task = fields.Many2One('process-process.step', 'Task')
    nb_tasks = fields.Integer('Number', depends=['task', 'kind'])
    kind = fields.Selection([('team', 'Team'), ('process', 'Process')], 'Kind',
        states={'invisible': True})
    task_name = fields.Function(
        fields.Char('Task Name', depends=['task']),
        'on_change_with_task_name')

    @fields.depends('task')
    def on_change_with_task_name(self, name=None):
        if not (hasattr(self, 'task') and self.task):
            return ''
        return '%s - %s' % (self.task.process.fancy_name,
            self.task.step.fancy_name)

    @fields.depends('task')
    def on_change_with_nb_tasks(self):
        if not (hasattr(self, 'task') and self.task):
            return None
        Log = Pool().get('process.log')
        return Log.search_count([
            ('latest', '=', True),
            ('to_state', '=', self.task),
            ('locked', '=', False)])


class TaskSelector(model.CoopView):
    'Task Selector'

    __name__ = 'task.select.available_tasks'

    team = fields.Many2One('res.team', 'Team')
    process = fields.Many2One('process', 'Process')
    nb_tasks_team = fields.Integer('Team Tasks', states={'readonly': True})
    nb_users_team = fields.Integer('Team Users', states={'readonly': True})
    nb_tasks_process = fields.Integer('Process Tasks',
        states={'readonly': True})
    tasks_team = fields.One2ManyDomain('task.select.available_tasks.task', '',
        'Team Tasks', domain=[('kind', '=', 'team')],
        states={'readonly': True})
    tasks_process = fields.One2ManyDomain('task.select.available_tasks.task',
        '', 'Process Tasks', domain=[('kind', '=', 'process')],
        states={'readonly': True})
    tasks = fields.One2Many('process.log', '', 'Tasks',
        domain=[('latest', '=', True), ('locked', '=', False)],
        order=[('priority', 'ASC')])
    selected_task = fields.Many2One('process.log', 'Selected Task',
        states={'readonly': True})

    @fields.depends('team', 'nb_tasks_team', 'nb_users_team', 'tasks_team',
        'tasks')
    def on_change_team(self):
        if not (hasattr(self, 'team') and self.team):
            return {
                'nb_users_team': 0,
                'nb_tasks_team': 0,
                'tasks_team': []}
        User = Pool().get('res.user')
        Log = Pool().get('process.log')
        result = {}
        result['nb_users_team'] = User.search_count([('team', '=', self.team)])
        tmp_result = {}
        final_result = []
        nb_tasks = 0
        TaskDisplayer = Pool().get('task.select.available_tasks.task')
        valid_states = []
        for priority in self.team.priorities:
            if (priority.process_step.id, priority.priority) in tmp_result:
                continue
            task = TaskDisplayer()
            task.kind = 'team'
            task.task = priority.process_step
            task.task_name = '%s - %s' % (task.task.process.fancy_name,
                task.task.step.fancy_name)
            task.nb_tasks = task.on_change_with_nb_tasks()
            nb_tasks += task.nb_tasks
            tmp_result[(priority.process_step.id, priority.priority)] = task
            final_result.append(task)
            valid_states.append(priority.process_step.id)
        result['tasks_team'] = model.serialize_this(final_result)
        result['nb_tasks_team'] = nb_tasks
        result['tasks'] = model.serialize_this(Log.search([
                ('latest', '=', True), ('locked', '=', False),
                ('to_state', 'in', valid_states)],
                order=[('priority', 'ASC')]))
        if not (hasattr(self, 'selected_task') and self.selected_task):
            result['selected_task'] = \
                result['tasks'][0] if result['tasks'] else None
        return result

    @fields.depends('process', 'nb_tasks_process', 'tasks_process')
    def on_change_process(self):
        if not (hasattr(self, 'process') and self.process):
            return {
                'nb_tasks_process': 0,
                'tasks_process': []}
        result = {}
        tmp_result = []
        nb_tasks = 0
        TaskDisplayer = Pool().get('task.select.available_tasks.task')
        for step in self.process.all_steps:
            task = TaskDisplayer()
            task.kind = 'process'
            task.task = step.id
            task.task_name = '%s - %s' % (task.task.process.fancy_name,
                task.task.step.fancy_name)
            task.nb_tasks = task.on_change_with_nb_tasks()
            nb_tasks += task.nb_tasks
            tmp_result.append(task)
        result['tasks_process'] = model.serialize_this(tmp_result)
        result['nb_tasks_process'] = nb_tasks
        return result

    @fields.depends('selected_task', 'tasks')
    def on_change_tasks(self):
        if not (hasattr(self, 'tasks') and self.tasks):
            return None
        found = None
        for task in self.tasks:
            if task.task_selected:
                if not(hasattr(self, 'selected_task') and self.selected_task) \
                        or task.id != self.selected_task.id:
                    found = task
        if not found:
            if hasattr(self, 'selected_task') and self.selected_task:
                found = self.selected_task
            else:
                return None
        result = {}
        result['selected_task'] = found.id
        result['tasks'] = {
            'update': [
                {'id': x.id, 'task_selected': x.id == found.id}
                for x in self.tasks]}
        return result


class TaskDispatcher(Wizard):
    'Task Dispatcher'

    __name__ = 'task.select'

    start_state = 'remove_locks'

    class VoidStateAction(StateAction):
        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            return None

    remove_locks = StateTransition()
    select_context = StateView('task.select.available_tasks',
        'task_manager.task_selector_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Compute Task', 'calculate_action', 'tryton-ok'),
            ])
    calculate_action = VoidStateAction()

    @classmethod
    def __setup__(cls):
        super(TaskDispatcher, cls).__setup__()
        cls._error_messages.update({
                'no_task_selected': 'No task has been selected.',
                })

    def default_select_context(self, name):
        Selector = Pool().get('task.select.available_tasks')
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
        for k, v in changes.iteritems():
            setattr(selector, k, v)
        return model.serialize_this(selector)

    def transition_remove_locks(self):
        Log = Pool().get('process.log')
        locked = Log.search([
            ('locked', '=', True),
            ('user', '=', Transaction().user)])
        if locked:
            Log.write(locked, {'locked': False})
        return 'select_context'

    def do_calculate_action(self, action):
        Log = Pool().get('process.log')
        if self.select_context.selected_task:
            good_task = self.select_context.selected_task
            good_id = good_task.task.id
            good_model = good_task.task.__name__
            act = good_task.to_state.process.get_act_window()
        else:
            self.raise_user_error('no_task_selected')

        Action = Pool().get('ir.action')
        act = Action.get_action_values(act.__name__, [act.id])[0]

        Session = Pool().get('ir.session')
        good_session, = Session.search(
            [('create_uid', '=', Transaction().user)])
        GoodModel = Pool().get(good_model)
        good_object = GoodModel(good_id)
        new_log = Log()
        new_log.user = Transaction().user
        new_log.locked = True
        new_log.task = good_object
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
        res = (act, {
                'id': good_id,
                'model': good_model,
                'res_id': good_id,
                'res_model': good_model,
                })
        return res


class LaunchTask(Wizard):
    'Launch Selected Task'

    __name__ = 'task.launch'

    start_state = 'calculate_action'
    calculate_action = StateAction('process_cog.act_resume_process')

    def do_calculate_action(self, action):
        active_id = Transaction().context.get('active_id')
        active_model = Transaction().context.get('active_model')
        log = Pool().get(active_model)(active_id)

        return (action, {
                'id': log.task.id,
                'model': log.task.__name__,
                'res_id': log.task.id,
                'res_model': log.task.__name__,
                })
