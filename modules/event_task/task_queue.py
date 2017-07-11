# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import inspect

from trytond.pool import Pool
from trytond.pyson import Eval, Not, Bool
from trytond.cache import Cache


from trytond.modules.coog_core import fields, model

__all__ = [
    'TaskQueueDefinition',
    'TaskQueueDefinitionParameter',
    ]


class TaskQueueDefinition(model.CoogSQL, model.CoogView):
    'Task Queue Definition'
    __name__ = 'task.queue.definition'

    order = fields.Integer('Order', states={'invisible': True})
    event_type_action = fields.Many2One('event.type.action',
        'Event Type Action', ondelete='CASCADE', required=True, select=True)
    available_batches = fields.Function(fields.Many2Many(
            'ir.model', None, None, 'Available Batches'),
        'get_available_batches')
    batch = fields.Many2One('ir.model', 'Batch', required=True,
        domain=[('id', 'in', Eval('available_batches'))],
        ondelete='CASCADE', depends=['available_batches'])
    task_queue_model = fields.Function(fields.Many2One('ir.model',
        'Task Queue Model',
        states={'invisible': Not(Bool(Eval('batch')))}, depends=['batch']),
        'on_change_with_task_queue_model')
    parameters = fields.One2Many('task.queue.definition.parameter',
        'definition', 'Parameters', delete_missing=True)
    _cached_batches = Cache('_cached_batches')

    @fields.depends('batch')
    def on_change_with_task_queue_model(self, name=None):
        pool = Pool()
        Model = pool.get('ir.model')
        if not self.batch:
            return
        target_model = pool.get(self.batch.model)
        target_name = getattr(target_model,
            'get_batch_main_model_name')()
        return Model.search([('model', '=', target_name)],
            limit=1)[0].id

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
            params = [x for x in func_params.args if x not in excluded_params]
            if only_required and func_params.defaults:
                used_params.update(set(params[:(len(func_params.args) -
                    len(func_params.defaults) - len(excluded_params))]))
            else:
                used_params.update(set(params))
        return used_params

    @fields.depends('batch')
    def on_change_with_parameters(self, name=None):
        if not self.batch:
            return []
        cur_model = Pool().get(self.batch.model)
        excluded_params = ['cls', 'objects', 'ids']
        used_params = self.get_used_params(cur_model, excluded_params)
        params = []
        self.parameters = []
        for name in used_params:
            params.append({'code': name, 'value': ''})
        return params

    @classmethod
    def default_available_batches(cls):
        return cls.get_available_batches()

    @classmethod
    def get_available_batches(cls, records=None, name=None):
        pool = Pool()
        models = []

        values = cls._cached_batches.get('batches', None)
        if not values:
            for model_ in pool.get('ir.model').search([]):
                try:
                    models.append((pool.get(model_.model), model_))
                except Exception:
                    pass

            values = [x[1].id for x in models
                if hasattr(x[0], 'get_batch_main_model_name')]
            cls._cached_batches.set('batches', values)
        if not records:
            return values
        return {x.id: list(values) for x in records}


@model.genshi_evaluated_fields('value')
class TaskQueueDefinitionParameter(model.CoogSQL, model.CoogView):
    'Task Queue Definition Parameter'
    __name__ = 'task.queue.definition.parameter'

    definition = fields.Many2One('task.queue.definition', 'Definition',
        required=True, ondelete='CASCADE', select=True)
    code = fields.Char('Code', required=True)
    value = fields.Char('Value',
        help='Genshi syntax is supported. Records are available as \'records\''
        )
