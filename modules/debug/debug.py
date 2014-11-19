from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import Eval, Bool


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
            'invisible': ~Bool(Eval('id_to_calculate', False))},
        help="Use the 'instance' keyword to get the instanciated model",
        depends=['id_to_calculate'])
    evaluation_result = fields.Char('Evaluation Result', states={
            'invisible': ~Bool(Eval('id_to_calculate', False))},
        readonly=True, depends=['id_to_calculate'])

    @classmethod
    def get_possible_model_names(cls):
        pool = Pool()
        return list([(x, x) for x in
                pool._pool[pool.database_name]['model'].iterkeys()])

    def get_field_info(self, field, field_name):
        info = Pool().get('ir.model.debug.model_info.field_info')()
        info.name = field_name
        info.string = field.string
        if isinstance(field, fields.Function):
            if self.hide_functions:
                return None
            info.is_function = True
            real_field = field._field
        else:
            info.is_function = False
            real_field = field
        info.kind = real_field.__class__.__name__
        if isinstance(field, (fields.Many2One, fields.One2Many)):
            info.target_model = field.model_name
        elif isinstance(field, fields.Many2Many):
            info.target_model = Pool().get(field.relation_name)._fields[
                field.target].model_name
        else:
            info.target_model = ''
        for elem in ('required', 'readonly', 'invisible'):
            setattr(info, 'is_%s' % elem, getattr(field, elem, False))
            setattr(info, 'state_%s' % elem, repr(field.states.get(elem, {})))
        field_domain = getattr(field, 'domain', None)
        if field_domain:
            info.has_domain = True
            info.field_domain = repr(field_domain)
        return info

    @classmethod
    def default_filter_value(cls):
        return 'name'

    @fields.depends('model_name', 'hide_functions', 'filter_value',
        'field_infos', 'id_to_calculate')
    def on_change_filter_value(self):
        self.recalculate_field_infos()

    @fields.depends('model_name', 'hide_functions', 'filter_value',
        'field_infos', 'id_to_calculate')
    def on_change_hide_functions(self):
        self.recalculate_field_infos()

    @fields.depends('model_name', 'hide_functions', 'filter_value',
        'field_infos', 'id_to_calculate')
    def on_change_model_name(self):
        self.id_to_calculate = None
        self.to_evaluate = ''
        self.evaluation_result = ''
        self.recalculate_field_infos()

    @fields.depends('model_name', 'id_to_calculate', 'to_evaluate')
    def on_change_with_evaluation_result(self):
        if (not self.id_to_calculate or not self.to_evaluate or not
                self.model_name):
            return ''
        try:
            context = {
                'instance': Pool().get(self.model_name)(self.id_to_calculate),
                }
            return str(eval(self.to_evaluate, context))
        except Exception, exc:
            return 'ERROR: %s' % str(exc)

    def recalculate_field_infos(self):
        self.field_infos = []
        if not self.model_name:
            return
        TargetModel = Pool().get(self.model_name)
        all_fields_infos = [self.get_field_info(field, field_name)
                for field_name, field in TargetModel._fields.iteritems()]
        self.field_infos = sorted(
            [x for x in all_fields_infos if x is not None],
            key=lambda x: getattr(x, self.filter_value))
        if self.id_to_calculate:
            for field in self.field_infos:
                try:
                    field.calculated_value = str(getattr(
                            TargetModel(self.id_to_calculate), field.name))
                except Exception, exc:
                    field.calculated_value = 'ERROR: %s' % str(exc)


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
        ModelData = Pool().get('ir.model.data')
        to_sync = ModelData.search([('out_of_sync', '=', True)])
        if to_sync:
            ModelData.sync(to_sync)
        return ''

    def transition_run(self):
        return 'display'

    def default_display(self, name):
        return {'result': self.run_code()}
