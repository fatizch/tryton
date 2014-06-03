from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import Eval


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
    state_required = fields.Text('State Required')
    is_required = fields.Boolean('Is required')
    state_readonly = fields.Text('State Readonly')
    is_readonly = fields.Boolean('Is readonly')
    state_invisible = fields.Text('State Invisible')
    is_invisible = fields.Boolean('Is invisible')
    has_domain = fields.Boolean('Has domain')
    field_domain = fields.Text('Domain')
    id_to_calculate = fields.Integer('Id To Calculate')
    calculated_value = fields.Char('Calculated Value')


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
    id_to_calculate = fields.Integer('Id To Calculate')
    to_evaluate = fields.Char('To Evaluate', states={
            'invisible': ~Eval('id_to_calculate', False)},
        depends=['id_to_calculate'])
    evaluation_result = fields.Char('Evaluation Result', states={
            'invisible': ~Eval('id_to_calculate', False),
            'readonly': True}, depends=['id_to_calculate'])

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
            result['state_%s' % elem] = repr(field.states.get(elem, {}))
        field_domain = getattr(field, 'domain', None)
        if field_domain:
            result['has_domain'] = True
            result['field_domain'] = repr(field_domain)
        return result

    @classmethod
    def default_filter_value(cls):
        return 'name'

    @fields.depends('model_name', 'field_infos', 'hide_functions',
        'filter_value', 'id_to_calculate')
    def on_change_with_field_infos(self):
        if self.field_infos:
            result = {'remove': [x.id for x in self.field_infos]}
        else:
            result = {}
        if not self.model_name:
            return result
        TargetModel = Pool().get(self.model_name)
        result['add'] = [(-1, x) for x in sorted(
                    filter(None,
                        list([self.get_field_info(field, field_name)
                                for field_name, field
                                in TargetModel._fields.iteritems()])),
                    key=lambda x: x[self.filter_value])]
        for k, v in result['add']:
            if self.id_to_calculate:
                try:
                    v['calculated_value'] = str(getattr(
                            TargetModel(self.id_to_calculate), v['name']))
                except:
                    v['calculated_value'] = 'Error calculating'
        return result

    @fields.depends('model_name', 'id_to_calculate', 'to_evaluate')
    def on_change_with_evaluation_result(self):
        if (not self.id_to_calculate or not self.to_evaluate or not
                self.model_name):
            return ''
        try:
            context = {
                'contract': Pool().get(self.model_name)(self.id_to_calculate),
                }
            return str(eval(self.to_evaluate, context))
        except:
            return 'Error'


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
        result['field_infos'] = [x[1] for x in
            self.model_info.on_change_with_field_infos()['add']]
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
