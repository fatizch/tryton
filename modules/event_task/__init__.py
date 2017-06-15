# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import event
import task_queue


def register():
    Pool.register(
        task_queue.TaskQueueDefinition,
        task_queue.TaskQueueDefinitionParameter,
        event.EventTypeAction,
        module='event_task', type_='model')
