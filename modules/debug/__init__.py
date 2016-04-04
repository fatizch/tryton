import inspect
import re
import logging

from trytond.pool import Pool
from .debug import *


def register():
    Pool.register(
        # From file debug
        FieldInfo,
        ModelInfo,
        VisualizeDebug,
        DebugModelInstance,
        DebugMROInstance,
        DebugMethodInstance,
        DebugMethodMROInstance,
        DebugFieldInstance,
        DebugViewInstance,
        DebugOnChangeRelation,
        DebugOnChangeWithRelation,
        module='debug', type_='model')

    Pool.register(
        # From file debug
        DebugModel,
        Debug,
        RefreshDebugData,
        OpenInitialFrame,
        module='debug', type_='wizard')

    Pool.register_post_init_hooks(set_method_names_for_profiling,
        module='debug')


def set_method_names_for_profiling(pool):
    '''
        Patches the pool initialization to separate given methods per model
        in @profile reports.

        Methods to patch are set in trytond.conf :

            [debug]
            methods=read,_validate,search,create,delete
    '''
    from trytond.config import config

    def change_method_name_for_profiling(klass, method_name):
        '''
            Override method_name in klass to use
            "<method_name>__<model_name>" as name in order to appear as a
            different line when profiling.
        '''
        if not hasattr(klass, method_name):
            return
        if method_name in klass.__dict__:
            return
        method = getattr(klass, method_name)
        if inspect.ismethod(method) and method.__self__ is klass:
            template = '@classmethod'
        else:
            template = ''
        template += '''
def %s(*args, **kwargs):
    return super(klass, args[0]).%s(*args[1:], **kwargs)
setattr(klass, method_name, %s)'''
        patched_name = method_name + '__' + re.sub(
            r'[^A-Za-z0-9]+', '_', klass.__name__)
        exec template % (patched_name, method_name, patched_name) in \
            {'klass': klass, 'method_name': method_name}, {}

    for meth_name in (config.get('debug', 'methods') or '').split(','):
        logging.getLogger().warning(
            'Patching %s for profiling, not recommanded for prod!'
            % meth_name)
        for klass in pool._pool[pool.database_name].get(
                'model', {}).values():
            change_method_name_for_profiling(klass, meth_name)
