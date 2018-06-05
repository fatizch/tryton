# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps
from celery.result import AsyncResult

from trytond.pyson import Eval
from trytond.pool import Pool

from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.config import config

from trytond.modules.coog_core import fields, model
import async.broker as async_broker

if not config.getboolean('env', 'testing'):
    async_broker.set_module('celery')
    broker = async_broker.get_module()


class CoogAsyncTask(model.CoogSQL):
    'Coog Async Task'
    __name__ = 'async.task'

    task_id = fields.Char('Task Id', readonly=True, required=True)
    origin = fields.Reference('Origin', selection='models_get', select=True,
        readonly=True, required=True)
    _queuable_models_get_cache = Cache('queuable_models_get')

    @classmethod
    def models_get(cls):
        models = cls._queuable_models_get_cache.get(None)
        if models:
            return models
        pool = Pool()
        Model = pool.get('ir.model')
        queueable = []
        for name, kls in pool.iterobject():
            if issubclass(kls, QueueMixin):
                queueable.append(name)
        res = sorted([(x.model, x.name) for x in Model.search(
                    ['model', 'in', queueable])],
            key=lambda x: x[1]) + [('', '')]
        cls._queuable_models_get_cache.set(None, res)
        return res

    @classmethod
    def delete_from_records(cls, records):
        to_remove = cls.search([('origin', 'in', [str(x) for x in records])])
        if to_remove:
            cls.delete(to_remove)


class QueueMixin(object):
    'Adds a Task Queue to a Model For Async Method Execution'

    async_tasks = fields.One2Many(
        'async.task', 'origin', 'Async Tasks', order=[('create_date', 'DESC')],
        delete_missing=True)
    current_async_task = fields.Function(
        fields.Many2One('async.task', 'Current Async Task',
            states={'invisible': ~Eval('current_async_task')}),
        'get_current_async_task')
    async_task_state = fields.Function(
        fields.Selection([
            ('PENDING', 'PENDING'),
            ('SUCCESS', 'SUCCESS'),
            ('FAILURE', 'FAILURE'),
            ('RETRY', 'RETRY'),
            ('REVOKED', 'REVOKED'),
            ], 'Current Async Task State',
            states={'invisible': ~Eval('current_async_task')},
            depends=['current_async_task'],
            ),
        'get_async_task_info')
    async_task_message = fields.Function(
        fields.Text('Current Async Task Description',
            states={'invisible': ~Eval('async_task_message')}),
        'get_async_task_info')

    @classmethod
    def __setup__(cls):
        super(QueueMixin, cls).__setup__()
        cls._error_messages.update({
                'async_job': ('This task will be applied in the backgound. '
                    'You can come back later and refresh the record to check '
                    'the result.'),
                'pending_task': ('This record has a pending background task '
                    '(technical id: %(id)s ).\nPlease wait for this task to '
                    'complete.'),
                'pending_tasks': ('The records below have pending background '
                    'tasks:\n\n%(names)s\n\nPlease wait for the tasks to '
                    'complete.'),
                'failed_task': ('The last background task failed. See below '
                    'for technical details:\n%(details)s'),
                })
        cls._async_methods = []

    @classmethod
    def check_pending_task(cls, records):
        context = Transaction().context
        from_async_worker = context.get('async_worker', False)
        if not from_async_worker:
            pendings = [x for x in records if x.has_pending_task]
            if pendings:
                cls.raise_user_error('pending_tasks',
                    {'names': '\n'.join(x.rec_name for x in pendings)})

    @classmethod
    def write(cls, *args, **kwargs):
        actions = iter(args)
        all_records = []
        for records, values in zip(actions, actions):
            all_records.extend(list(records))
        cls.check_pending_task(all_records)
        super(QueueMixin, cls).write(*args, **kwargs)

    @classmethod
    def delete(cls, *args, **kwargs):
        cls.check_pending_task(*args)
        super(QueueMixin, cls).delete(*args, **kwargs)

    @property
    def has_pending_task(self):
        return self.async_task_state in ('PENDING', 'STARTED', 'RETRY')

    def get_current_async_task(self, name):
        if self.async_tasks:
            return self.async_tasks[0].id

    def get_async_task_info(self, name):
        # N.B: if we had a failed task that was removed
        # from redis, it will still exist in database
        # and it will appear as 'PENDING', see:
        # http://docs.celeryproject.org/en/latest/userguide/tasks.html#pending
        # So, we will have to remove it manually from db.
        if not self.current_async_task:
            return ''
        assert broker.app
        async_res = AsyncResult(self.current_async_task.task_id, app=broker.app)
        state = async_res.state
        if name == 'async_task_state':
            return state
        elif name == 'async_task_message':
            if state == 'PENDING':
                return self.raise_user_error('pending_task',
                    {'id': async_res.id}, raise_exception=False)
            elif state == 'FAILURE':
                return self.raise_user_error('failed_task',
                    {'details': async_res.traceback},
                    raise_exception=False)
            return ''
        return ''

    @staticmethod
    def async_method(method_name, condition=None):
        """
        This decorator can be applied to classmethods on models
        who inherit from QueueMixin, so that the classmethod
        can be executed by a background celery worker.

        The basice use case is for methods with long running time.

        :condition [optional]: the name of an existing staticmethod
        on the model that takes the records on which the decorated method
        will be applied as parameter, and returns True or False.
        The decorated method will be executed by a background worker only
        if the condition returns True or if there is no condition.
        Otherwise, the method will run synchronously.
        """

        def build_async_function(func):

            # TODO: use wrapt.decorator to make it universal
            @wraps(func)
            def wrapper(cls, instances, *args, **kwargs):

                pool = Pool()
                AsyncTask = pool.get('async.task')
                context = Transaction().context
                if condition:
                    async_allowed = getattr(cls, condition)(instances)
                else:
                    async_allowed = True
                from_async_worker = context.get('async_worker', False)
                from_batch = context.get('from_batch', False)
                force_synchronous = context.get('force_synchronous', False)
                rollback = context.get('will_be_rollbacked', False)

                cls.check_pending_task(instances)

                if from_async_worker or from_batch or force_synchronous or \
                        not async_allowed or rollback:
                    res = func(instances, *args, **kwargs)
                    # Although we checked for pending tasks,
                    # we still have to remove the potential failed
                    # or succeeded tasks
                    AsyncTask.delete_from_records(instances)
                    return res

                cls.raise_user_warning('async_job_%s' % [str(x)
                            for x in instances], 'async_job')

                ids = [x.id for x in instances]
                enqueue_args = (ids, ) + args
                kwargs.update({
                        'user': Transaction().user,
                        'model_name': cls.__name__,
                        'method_name': method_name,
                        'database': pool.database_name})
                # TODO: manage this post transaction
                task_id = broker.enqueue(cls.__name__, 'async_method_execution',
                    enqueue_args, **kwargs)
                assert task_id
                to_save = []
                for record in instances:
                    to_save.append(AsyncTask(task_id=task_id,
                            origin=record))
                if to_save:
                    AsyncTask.save(to_save)
                return [x.id for x in instances]
            return wrapper
        return build_async_function


def async_methods_hook(pool, update):
    if update:
        return

    for klass in [x[1] for x in pool.iterobject()]:
        if not klass or not hasattr(klass, '_async_methods'):
            continue
        for meth, async_cond in klass._async_methods:
            original = getattr(klass, meth)
            setattr(klass, meth, classmethod(QueueMixin.async_method(
                        meth, async_cond)(original)))
