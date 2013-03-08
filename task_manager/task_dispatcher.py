import datetime

from trytond.wizard import Wizard, StateAction
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.coop_utils import utils


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
        Log = Pool().get('coop_process.process_log')
        locked = Log.search([
            ('locked', '=', True),
            ('user', '=', Transaction().user)])
        if locked:
            Log.write(locked, {'locked': False})

        if not action:
            self.raise_user_error('no_task_available')

        act, good_id, good_model = action
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
