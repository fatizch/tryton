# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import inspect

from trytond.pyson import Eval, Bool, Not
from trytond.pool import PoolMeta, Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.modules.coog_core import model, fields


__metaclass__ = PoolMeta
__all__ = [
    'LaunchBatch',
    'SelectBatch',
    'BatchParameter',
    ]


class LaunchBatch(Wizard):
    'Launch Batch'

    __name__ = 'batch.launcher'

    start = StateView('batch.launcher.select_batchs',
        'batch_launcher.batch_launcher_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'process', 'tryton-ok', default=True),
            ])
    process = StateTransition()

    @classmethod
    def __setup__(cls):
        super(LaunchBatch, cls).__setup__()
        logging.getLogger().warning(
            'Module shoud not be installed in production.')

    def transition_process(self):
        BatchModel = Pool().get(self.start.batch.model)
        for param in self.start.parameters:
            if param.code == 'treatment_date' and self.start.treatment_date:
                param.value = str(self.start.treatment_date)
                break
        self.check_required_params()
        extra_args = {p.code: p.value for p in self.start.parameters}
        ids = BatchModel.select_ids(**extra_args)
        objects = BatchModel.convert_to_instances([x[0] for x in ids]) \
            if ids else []
        BatchModel.execute(objects, [x[0] for x in ids], **extra_args)
        return 'end'

    def check_required_params(self):
        batch_model = Pool().get(self.start.batch.model)
        excluded_params = ['cls', 'objects', 'ids']
        used_params = self.start.get_used_params(batch_model, excluded_params,
            only_required=True)
        for param in self.start.parameters:
            if param.code in used_params and param.value == '':
                with model.error_manager():
                    self.start.append_functional_error('required_parameter',
                        {'param': param.code})

    @classmethod
    def possible_batches(cls):
        pool = Pool()
        models = []
        for model_ in pool.get('ir.model').search([]):
            try:
                models.append((pool.get(model_.model), model_))
            except Exception:
                # Some dirty models could remain in ir.model
                # even if the definition doesn't exist anymore
                # => ignoring it
                pass
        return [x[1] for x in models if cls.is_batch(x[0])]

    def default_start(self, fields):
        all_batches = self.possible_batches()
        loaded_parameters = []
        excluded_params = ['cls', 'objects', 'ids']
        for batch in all_batches:
            BatchModel = Pool().get(batch.model)
            used_params = self.start.get_used_params(BatchModel,
                excluded_params, only_required=False)
            for name in used_params:
                loaded_parameters.append({'code': name, 'value': ''})
        return {
            'available_batches': [x.id for x in all_batches],
            'parameters': [],
            'loaded_parameters': loaded_parameters,
            }

    @classmethod
    def is_batch(cls, model):
        return hasattr(model, 'get_batch_main_model_name')


class BatchParameter(model.CoogView):
    'Batch Parameter'

    __name__ = 'batch.launcher.parameter'
    code = fields.Char('Code', required=True, readonly=True,
        states={'invisible': Eval('code') == 'treatment_date'})
    value = fields.Char('Value',
        states={'invisible': Eval('code') == 'treatment_date'})


class SelectBatch(model.CoogView):
    'Select Batch'
    __name__ = 'batch.launcher.select_batchs'

    available_batches = fields.One2Many('ir.model', None, 'Available Batches')
    batch = fields.Many2One('ir.model', 'Batch', required=True,
        domain=[('id', 'in', Eval('available_batches'))],
        ondelete='CASCADE', depends=['available_batches'])
    on_model = fields.Function(fields.Many2One('ir.model', 'On model',
        states={'invisible': Not(Bool(Eval('batch')))}, depends=['batch']),
        'on_change_with_on_model')
    treatment_date = fields.Date('Treatment Date', states={
            'invisible': ~Eval('has_treatment_date')})
    parameters = fields.One2Many('batch.launcher.parameter', None,
        'Batch Parameters')
    loaded_parameters = fields.One2Many('batch.launcher.parameter', None,
        'Loaded Parameters')
    has_treatment_date = fields.Function(fields.Boolean('Has Treatment Date'),
        'on_change_with_has_treatment_date')

    @classmethod
    def __setup__(cls):
        super(SelectBatch, cls).__setup__()
        cls._error_messages.update({
            'required_parameter': 'Required parameter: %(param)s'
            })

    @fields.depends('batch')
    def on_change_with_on_model(self, name=None):
        pool = Pool()
        Model = pool.get('ir.model')
        LaunchBatch = pool.get('batch.launcher', type='wizard')
        if not self.batch:
            return
        target_model = pool.get(self.batch.model)
        if LaunchBatch.is_batch(target_model):
            try:
                target_name = getattr(target_model,
                    'get_batch_main_model_name')()
                return Model.search([('model', '=', target_name)],
                    limit=1)[0].id
            except:
                # The batch does not implement
                # get_batch_main_model_name() method
                # Ignoring...
                pass

    def get_from_loaded_parameters(self, code):
        for parameter in self.loaded_parameters:
            if parameter.code == code:
                return {'code': parameter.code, 'value': parameter.value}
        return None

    @fields.depends('batch', 'loaded_parameters')
    def on_change_with_parameters(self, name=None):
        if not self.batch:
            return []
        cur_model = Pool().get(self.batch.model)
        excluded_params = ['cls', 'objects', 'ids']
        used_params = self.get_used_params(cur_model, excluded_params,
            only_required=False)
        params = []
        for name in used_params:
            loaded = self.get_from_loaded_parameters(name)
            if loaded:
                params.append(loaded)
        return params

    @fields.depends('parameters', 'on_model')
    def on_change_with_has_treatment_date(self, name=None):
        for parameter in self.parameters:
            if parameter.code == 'treatment_date':
                return True
        return False

    @staticmethod
    def get_used_params(batch_model, excluded_params, only_required=False):
        '''
        This method returns the used parameters of a batch model using the
        batch function execute. With the Method Resolution Order function and
        the inspect package, it browses all parent models and the model itself
        in order to determine which parameters are used by the batch to run.
        This is done by dismissing 'cls', 'objects' and 'ids' from the
        'execute' function parameters and returning all other parameters.
        Furthermore, when the method's 'only_required' parameter is equal to
        True, it also dismisses parameters which have a default value.
        '''
        used_params = set()
        for klass in batch_model.__mro__:
            func = getattr(klass, 'execute', None)
            if func is None:
                continue
            func_params = inspect.getargspec(func)
            params = [x for x in func_params[0] if x not in excluded_params]
            if only_required and func_params.defaults:
                used_params.update(set(params[:(len(func_params.args) -
                    len(func_params.defaults) - len(excluded_params))]))
            else:
                used_params.update(set(params))
        return used_params
