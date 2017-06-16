# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.server_context import ServerContext
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, utils

__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction:
    __metaclass__ = PoolMeta
    __name__ = 'event.type.action'

    task_queues = fields.One2Many('task.queue.definition',
            'event_type_action', 'Task Queues',
        states={'invisible': Eval('action') != 'process_task'},
        order=[('order', 'ASC')], delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(EventTypeAction, cls).__setup__()
        cls._error_messages.update({'process_task': 'Process Task'})

    @classmethod
    def get_action_types(cls):
        return super(EventTypeAction, cls).get_action_types() + [
            ('process_task', cls.raise_user_error(
                    'process_task', raise_exception=False))]

    @fields.depends('report_templates')
    def on_change_action(self):
        super(EventTypeAction, self).on_change_action()
        self.task_queues = []
        self.treatment_kind = 'synchronous'

    def build_genshi_context(self, objects, event_code, *args, **kwargs):
        return {
            'records': objects,
            'event_code': event_code,
            'Today': utils.today,
            'user': Pool().get('res.user')(Transaction().user),
            }

    def execute(self, objects, event_code, description=None, **kwargs):
        if self.action != 'process_task':
            return super(EventTypeAction, self).execute(objects, event_code)
        pool = Pool()
        with ServerContext().set_context(
                genshi_context=self.build_genshi_context(objects, event_code,
                    **kwargs)):
            for queue in self.task_queues:
                parameters = {x.code: x.genshi_evaluated_value
                    for x in queue.parameters}
                batch = pool.get(queue.batch.model)
                batch.enqueue(
                    [(x.id,) for x in batch.enqueue_filter_objects(objects)
                        ], parameters, user=Transaction().user)
