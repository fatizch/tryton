from trytond.wizard import Wizard, StateAction
from trytond.transaction import Transaction
from trytond.pool import Pool


__all__ = [
    'TaskDispatcher',
]


class TaskDispatcher(Wizard):
    'Task Dispatcher'

    __name__ = 'task_manager.task_dispatcher'

    start_state = 'calculate_action'

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

    calculate_action = LaunchStateAction()

    @classmethod
    def __setup__(cls):
        super(TaskDispatcher, cls).__setup__()
        cls._error_messages.update({
            'no_task_available': 'There is no task available right now.',
        })

    def do_calculate_action(self, action):
        if not action:
            self.raise_user_error('no_task_available')

        act, good_id, good_model = action
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
