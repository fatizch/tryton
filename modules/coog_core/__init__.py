# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool
from trytond.config import config
from trytond.cache import Cache, freeze

import batch
import export
import ir
import res
import model
import test_case_framework
import models_for_tests
import tag
import event
import attachment
import diff_blame
import note
import access
import extra_details
import wizard_context
import test_case
import load_data
import queue

from model import UnionMixin, expand_tree

__all__ = [
    'UnionMixin',
    'expand_tree',
    ]


def register():
    Pool.register(
        export.ExportPackage,
        export.ExportInstance,
        export.ExportConfiguration,
        export.ExportModelConfiguration,
        export.ExportFieldConfiguration,
        export.ExportModelExportConfigurationRelation,
        export.ExportSelectFields,
        export.Add2ExportPackageWizardStart,
        tag.Tag,
        ir.Sequence,
        ir.SequenceStrict,
        ir.DateClass,
        ir.View,
        ir.UIMenu,
        ir.Rule,
        ir.RuleGroup,
        ir.Action,
        ir.ActionKeyword,
        ir.IrModule,
        ir.IrModel,
        ir.IrModelField,
        ir.IrModelFieldAccess,
        ir.ModelAccess,
        ir.Lang,
        ir.Icon,
        res.Group,
        res.User,
        res.ResUserWarning,
        export.FileSelector,
        batch.ViewValidationBatch,
        batch.CleanDatabaseBatch,
        batch.NoSelectBatchExample,
        batch.DataUpdateBatch,
        test_case_framework.TestCaseModel,
        test_case_framework.TestCaseInstance,
        test_case_framework.TestCaseRequirementRelation,
        test_case_framework.TestCaseSelector,
        test_case_framework.SelectTestCase,
        test_case_framework.TestCaseFileSelector,
        tag.TagObjectRelation,
        model.MethodDefinition,
        event.Event,
        event.EventType,
        event.EventTypeAction,
        event.ActionEventTypeRelation,
        export.ExportSummary,
        export.ExportConfigurationSelection,
        ir.Translation,
        ir.TranslationOverrideStart,
        attachment.Attachment,
        diff_blame.RevisionBlame,
        diff_blame.RevisionFormatTranslator,
        note.Note,
        access.Model,
        access.ModelField,
        access.UIMenuAccess,
        batch.BatchParamsConfig,
        extra_details.ExtraDetailsConfiguration,
        extra_details.ExtraDetailsConfigurationLine,
        wizard_context.PersistentDataView,
        test_case.TestCaseModel,
        load_data.GlobalSearchSet,
        load_data.LanguageTranslatableSet,
        queue.CoogAsyncTask,
        module='coog_core', type_='model')

    if config.getboolean('env', 'testing') is True:
        Pool.register(
            models_for_tests.TestMethodDefinitions,
            models_for_tests.TestDictSchema,
            models_for_tests.ExportTestTarget,
            models_for_tests.ExportTestTargetSlave,
            models_for_tests.ExportTest,
            models_for_tests.ExportTestTarget2,
            models_for_tests.ExportTestTargetSlave2,
            models_for_tests.ExportTestRelation,
            models_for_tests.ExportTestM2O,
            models_for_tests.ExportTestNumeric,
            models_for_tests.ExportTestChar,
            models_for_tests.ExportTestSelection,
            models_for_tests.O2MDeletionMaster,
            models_for_tests.O2MDeletionChild,
            models_for_tests.TestHistoryTable,
            models_for_tests.TestHistoryChildTable,
            models_for_tests.TestLoaderUpdater,
            module='coog_core', type_='model')

    Pool.register(
        export.ImportWizard,
        export.Add2ExportPackageWizard,
        test_case_framework.TestCaseWizard,
        export.ExportFieldsSelection,
        export.ExportToFile,
        ir.TranslationOverride,
        diff_blame.RevisionBlameWizard,
        wizard_context.PersistentContextWizard,
        load_data.GlobalSearchSetWizard,
        load_data.LanguageTranslatableWizard,
        module='coog_core', type_='wizard')

    Pool.register_post_init_hooks(cache_fields_get, module='ir')
    Pool.register_post_init_hooks(event_process_buttons, module='process')
    Pool.register_post_init_hooks(add_global_search_limit, module='coog_core')
    Pool.register_post_init_hooks(add_readonly_transaction_model,
        module='coog_core')


def cache_fields_get(pool, update):
    from trytond.model import Model

    if hasattr(Model, '_fields_get_cache'):
        return

    logging.getLogger('modules').info('Running post init hook %s' %
        'cache_fields_get')
    Model._fields_get_cache = Cache('fields_get_cache')
    fields_get_orig = Model.fields_get.__func__

    @classmethod
    def patched_fields_get(cls, fields_names=None):
        key = freeze((cls.__name__, set(fields_names or [])))
        cached_value = cls._fields_get_cache.get(key, None)
        if cached_value:
            return cached_value
        res = fields_get_orig(cls, fields_names)
        cls._fields_get_cache.set(key, res)
        return res

    Model.fields_get = patched_fields_get


def event_process_buttons(pool, update):
    # We allow process classes to handle dynamic buttons to trigger events.
    # The pattern _button_event_<event_code> is used for detection
    Module = pool.get('ir.module')
    process = Module.search([('name', '=', 'process'),
            ('state', '=', 'activated')])
    if not process:
        return

    from trytond.modules.process.process_framework import ProcessFramework
    if hasattr(ProcessFramework, '__event_button_patched'):
        return

    logging.getLogger('modules').info('Adding event button on processes')
    orig_button_method = ProcessFramework._default_button_method.__func__
    orig_button_states = ProcessFramework.calculate_button_states.__func__

    def get_event_method(code):
        def event_method(instances):
            pool.get('event').notify_events(instances, code)
        return event_method

    @classmethod
    def patched_method(cls, button_name):
        data = button_name.split('_')
        if data[0] != 'event':
            return orig_button_method(cls, button_name)
        return get_event_method('_'.join(data[1:]))

    @classmethod
    def patched_states(cls, button_data):
        if button_data[0] != 'event':
            return orig_button_states(cls, button_data)
        return {}

    ProcessFramework._default_button_method = patched_method
    ProcessFramework.calculate_button_states = patched_states
    ProcessFramework.__event_button_patched = True


def inject_class(pool, kind, source, target, model_list=None):
    '''
        Inject the "target" dependency in place of the "source" in models
        matching "kind".

        Typical use case would be to add a TestMixin to all ModelSQL
        objects (assuming TestMixin inherits from ModelSQL) :

            inject_class(pool, 'model', ModelSQL, TestMixin)

        'kind' may be one of 'model', 'report', 'wizard', or 'manual'. If
        'manual' is set, the optional 'model_list' arguments is used to define
        which models should be updated.
    '''
    def patch_model(klass):
        if issubclass(klass, target) or not issubclass(klass, source):
            return
        for mro_class in reversed(klass.__mro__):
            if mro_class == source:
                continue
            if source not in mro_class.__bases__:
                continue
            mro_class.__bases__ = tuple(
                x if x != source else target
                for x in mro_class.__bases__)

    assert kind in ('model', 'report', 'wizard', 'manual')
    if kind == 'manual':
        assert model_list is not None
        for elem in model_list:
            model = pool._pool[pool.database_name].get('model').get(elem)
            patch_model(model)
    else:
        for model in pool._pool[pool.database_name].get(
                kind, {}).values():
            patch_model(model)


def add_global_search_limit(pool, update):
    if update:
        return
    from trytond.model import ModelStorage
    from trytond.modules.coog_core.model import GlobalSearchLimitedMixin

    logging.getLogger('modules').info('Limiting global search on all models')
    inject_class(pool, 'model', ModelStorage, GlobalSearchLimitedMixin)


def add_readonly_transaction_model(pool, update):
    if update:
        return
    from trytond.model import ModelStorage
    from trytond.modules.coog_core.model import DynamicReadonlyTransactionMixin

    logging.getLogger('modules').info('Adding readonly transaction model mode')
    inject_class(pool, 'model', ModelStorage, DynamicReadonlyTransactionMixin)
