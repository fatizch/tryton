from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.pool import Pool


__all__ = [
    'FieldInfo',
    'ModelInfo',
    'DebugModel',
    'VisualizeDebug',
    'Debug',
    ]


class FieldInfo(ModelView):
    'Field Info'

    __name__ = 'ir.model.debug.model_info.field_info'

    name = fields.Char('Field name')
    kind = fields.Char('Field type')
    is_function = fields.Boolean('Is Function')
    target_model = fields.Char('Target Model')
    string = fields.Char('String')
    state_required = fields.Text('States Required')
    is_required = fields.Boolean('Is required')
    state_readonly = fields.Text('States Readonly')
    is_readonly = fields.Boolean('Is readonly')
    state_invisible = fields.Text('States Invisible')
    is_invisible = fields.Boolean('Is invisible')


class ModelInfo(ModelView):
    'Model Name'

    __name__ = 'ir.model.debug.model_info'

    model_name = fields.Selection('get_possible_model_names', 'Model Name')
    field_infos = fields.One2Many('ir.model.debug.model_info.field_info',
        '', 'Fields Infos')
    hide_functions = fields.Boolean('Hide Functions')
    filter_value = fields.Selection([
            ('name', 'Name'),
            ('kind', 'Kind'),
            ('string', 'String')], 'Filter Value')

    @classmethod
    def get_possible_model_names(cls):
        pool = Pool()
        return list([(x, x) for x in
                pool._pool[pool.database_name]['model'].iterkeys()])

    def get_field_info(self, field, field_name):
        result = {'name': field_name, 'string': field.string}
        if isinstance(field, fields.Function):
            if self.hide_functions:
                return None
            result['is_function'] = True
            real_field = field._field
        else:
            result['is_function'] = False
            real_field = field
        result['kind'] = real_field.__class__.__name__
        if isinstance(field, (fields.Many2One, fields.One2Many)):
            result['target_model'] = field.model_name
        else:
            result['target_model'] = ''
        for elem in ('required', 'readonly', 'invisible'):
            result['is_%s' % elem] = getattr(field, elem, False)
            result['state_%s' % elem] = field.states.get(elem, {}).__repr__()
        return result

    @classmethod
    def default_filter_value(cls):
        return 'name'

    @fields.depends('model_name', 'field_infos', 'hide_functions',
        'filter_value')
    def on_change_with_field_infos(self):
        TargetModel = Pool().get(self.model_name)
        if self.field_infos:
            result = {'remove': [x.id for x in self.field_infos]}
        else:
            result = {}
        if not self.model_name:
            return result
        result['add'] = sorted(
            filter(None,
                list([self.get_field_info(field, field_name)
                        for field_name, field
                        in TargetModel._fields.iteritems()])),
            key=lambda x: x[self.filter_value])
        return result


class DebugModel(Wizard):
    'Debug Model'

    __name__ = 'ir.model.debug'

    start_state = 'model_info'
    model_info = StateView('ir.model.debug.model_info',
        'debug.model_info_view_form',
        [Button('Quit', 'end', 'tryton-cancel')])

    def default_model_info(self, name):
        if self.model_info and getattr(self.model_info, 'model_name', None):
            return self.model_info._default_values
        if Transaction().context.get('active_model', '') != 'ir.model':
            return {}
        self.model_info.model_name = Pool().get('ir.model')(
            Transaction().context.get('active_id')).model
        self.model_info.hide_functions = False
        self.model_info.filter_value = 'name'
        result = self.model_info._default_values
        result['field_infos'] = self.model_info.on_change_with_field_infos(
            )['add']
        return result


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
