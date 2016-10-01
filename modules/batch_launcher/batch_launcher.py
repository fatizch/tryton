# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from datetime import datetime
import logging

from trytond.pyson import Eval, Bool, Not
from trytond.pool import PoolMeta, Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.modules.coog_core import model, fields, utils


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
        treatment_date = datetime.strptime(str(self.start.treatment_date),
            '%Y-%m-%d').date()
        BatchModel = Pool().get(self.start.batch.model)
        extra_args = {p.code: p.value for p in self.start.parameters}
        ids = BatchModel.select_ids(treatment_date, extra_args)
        objects = BatchModel.convert_to_instances((x[0] for x in ids)) \
            if ids else []
        BatchModel.execute(objects, ids, treatment_date, extra_args)
        return 'end'

    @classmethod
    def possible_batches(cls):
        pool = Pool()
        models = []
        for model_ in pool.get('ir.model').search([]):
            try:
                models.append((pool.get(model.model), model_))
            except Exception:
                # Some dirty models could remain in ir.model
                # even if the definition doesn't exist anymore
                # => ignoring it
                pass
        return [x[1] for x in models if cls.is_batch(x[0])]

    def default_start(self, fields):
        all_batches = self.possible_batches()
        loaded_parameters = []
        for batch in all_batches:
            BatchModel = Pool().get(batch.model)
            for name in BatchModel.get_batch_args_name():
                loaded_parameters.append({'code': name, 'value': ''})
        return {
            'treatment_date': utils.today(),
            'available_batches': [x.id for x in all_batches],
            'parameters': [],
            'loaded_parameters': loaded_parameters,
            }

    @classmethod
    def is_batch(cls, model):
        return hasattr(model, 'get_batch_main_model_name') and \
            hasattr(model, 'get_batch_args_name')


class BatchParameter(model.CoogView):
    'Batch Parameter'

    __name__ = 'batch.launcher.parameter'
    code = fields.Char('Code', required=True, readonly=True)
    value = fields.Char('Value')


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
    treatment_date = fields.Date('Treatment Date', required=True)
    parameters = fields.One2Many('batch.launcher.parameter', None,
        'Batch Parameters')
    loaded_parameters = fields.One2Many('batch.launcher.parameter', None,
        'Loaded Parameters')

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
        pool = Pool()
        batch_parameters = pool.get(self.batch.model).get_batch_args_name()
        params = []
        for name in batch_parameters:
            loaded = self.get_from_loaded_parameters(name)
            if loaded:
                params.append(loaded)
        return params
