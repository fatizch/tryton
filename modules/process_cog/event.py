# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby

from trytond.pyson import Eval, Or, If
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields


__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction:

    __metaclass__ = PoolMeta
    __name__ = 'event.type.action'

    process_to_initiate = fields.Many2One('process', 'Process To Initiate',
        ondelete='RESTRICT', states={
            'invisible': Eval('action') != 'initiate_process',
            'required': Eval('action') == 'initiate_process'})
    step_to_start = fields.Many2One('process-process.step', 'Step to start',
        domain=[If(~Eval('process_to_initiate'), [],
                [('process', '=', Eval('process_to_initiate'))])],
        ondelete='SET NULL', states={
            'invisible': ~Eval('process_to_initiate'),
            }, depends=['process_to_initiate'])
    filter_on_event_object = fields.Boolean('Filter On Event Object',
        help="If checked, the pyson condition will apply on the original"
        " object of the event. Otherwise, the condition will apply on the"
        " object of the process.", states={
            'invisible': Or(~Eval('pyson_condition'),
                Eval('action') != 'initiate_process')},
        depends=['pyson_condition', 'action'])

    @classmethod
    def __setup__(cls):
        super(EventTypeAction, cls).__setup__()
        cls._error_messages.update({'initiate_process': 'Initiate Process'})
        cls._error_messages.update({'clear_process': 'Clear Process'})

    @fields.depends('process_to_initiate', 'step_to_start')
    def on_change_process_to_initiate(self):
        if not self.process_to_initiate:
            self.step_to_start = None

    @classmethod
    def get_action_types(cls):
        return super(EventTypeAction, cls).get_action_types() + [
            ('initiate_process', cls.raise_user_error(
                    'initiate_process', raise_exception=False)),
            ('clear_process', cls.raise_user_error(
                    'clear_process', raise_exception=False))]

    @classmethod
    def _export_light(cls):
        return super(EventTypeAction, cls)._export_light() | {
            'process_to_initiate', 'step_to_start'}

    def get_objects_for_process(self, objects, target_model_name):
        raise NotImplementedError

    def filter_objects(self, objects):
        if self.action != 'initiate_process':
            return super(EventTypeAction, self).filter_objects(objects)
        event_obj_name = objects[0].__name__
        process_model_name = self.process_to_initiate.on_model.model
        if event_obj_name != process_model_name:
            if self.filter_on_event_object:
                objects = super(EventTypeAction, self).filter_objects(objects)
            process_objects = self.get_objects_for_process(objects,
                process_model_name)
            if self.filter_on_event_object:
                return process_objects
        else:
            process_objects = objects
        return super(EventTypeAction, self).filter_objects(process_objects)

    def execute(self, objects, event_code, description=None, **kwargs):
        if self.action == 'clear_process':
            return self._action_clear_process(objects, event_code, description,
                **kwargs)
        elif self.action == 'initiate_process':
            return self._action_initiate_process(objects, event_code,
                description, **kwargs)
        else:
            return super(EventTypeAction, self).execute(objects, event_code)

    def _action_clear_process(self, objects, event_code, description,
            **kwargs):
        pool = Pool()

        def keyfunc(x):
            return x.__name__

        objects.sort(key=keyfunc)
        for name, group in groupby(objects, key=keyfunc):
            pool.get(name).write(list(group), {'current_state': None})

    def _action_initiate_process(self, objects, event_code, description,
            **kwargs):
        pool = Pool()
        Event = pool.get('event')
        process = self.process_to_initiate
        process_model_name = process.on_model.model
        state = self.step_to_start or process.first_step()
        ok, not_ok = [], []
        [ok.append(x) if not x.current_state else not_ok.append(x)
            for x in objects]
        if ok:
            ProcessModel = pool.get(process_model_name)
            with Transaction().set_context(set_empty_process_user=True):
                ProcessModel.write(ok, {'current_state': state})
        if not_ok:
            Event.notify_events(not_ok, 'process_not_initiated',
                description=process.technical_name)

    def cache_data(self):
        data = super(EventTypeAction, self).cache_data()
        data['process_to_initiate'] = self.process_to_initiate.id if \
            self.process_to_initiate else None
        return data
