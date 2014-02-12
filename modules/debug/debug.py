from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool


__all__ = [
    'VisualizeDebug',
    'Debug',
    ]


class VisualizeDebug(ModelView):
    'Debug Visualize'

    __name__ = 'debug.visualize'

    result = fields.Text('Result')


class Debug(Wizard):
    'Debug'

    __name__ = 'debug'

    start_state = 'run'
    run = StateTransition()
    display = StateView('debug.visualize', 'debug.visualize_view_form',
        [Button('Quit', 'end', 'tryton-cancel'),
            Button('Re-Run', 'run', 'tryton-go-next')])

    def run_code(self):
        # Run your code. return value will be wrote down in the display window
        result = '\n'.join([x.name for x in Pool().get('ir.model').search([])])
        Move = Pool().get('account.move')
        print Move
        print dir(Move)
        print Move.get_publishing_values
        print Move.__mro__
        return result

    def transition_run(self):
        return 'display'

    def default_display(self, name):
        return {'result': self.run_code()}
