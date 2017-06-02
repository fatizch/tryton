# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool
from trytond.config import config
from trytond.cache import Cache, freeze

from .batch import *
from .utils import *
from .coog_date import *
from .coog_string import *
from .export import *
from .ir import *
from .res import *
from .model import *
from .many2one_form import *
from .test_case_framework import *
from .models_for_tests import *
from .tag import *
from .event import *
from .attachment import *
from .diff_blame import *
from .note import *
from .access import *
import extra_details
import wizard_context


def register():
    Pool.register(
        ExportPackage,
        ExportInstance,
        ExportConfiguration,
        ExportModelConfiguration,
        ExportFieldConfiguration,
        ExportModelExportConfigurationRelation,
        ExportSelectFields,
        Add2ExportPackageWizardStart,
        Tag,
        Sequence,
        SequenceStrict,
        DateClass,
        View,
        UIMenu,
        Rule,
        RuleGroup,
        Action,
        ActionKeyword,
        IrModule,
        IrModel,
        IrModelField,
        IrModelFieldAccess,
        ModelAccess,
        Property,
        Lang,
        Icon,
        Group,
        User,
        ResUserWarning,
        FileSelector,
        ViewValidationBatch,
        CleanDatabaseBatch,
        NoSelectBatchExample,
        TestCaseModel,
        TestCaseInstance,
        TestCaseRequirementRelation,
        TestCaseSelector,
        SelectTestCase,
        TestCaseFileSelector,
        TagObjectRelation,
        MethodDefinition,
        Event,
        EventType,
        EventTypeAction,
        ActionEventTypeRelation,
        ExportSummary,
        ExportConfigurationSelection,
        Translation,
        TranslationOverrideStart,
        Attachment,
        RevisionBlame,
        RevisionFormatTranslator,
        Note,
        Model,
        ModelField,
        UIMenuAccess,
        BatchParamsConfig,
        extra_details.ExtraDetailsConfiguration,
        extra_details.ExtraDetailsConfigurationLine,
        wizard_context.PersistentDataView,
        module='coog_core', type_='model')

    if config.get('env', 'testing') == 'True':
        Pool.register(
            TestMethodDefinitions,
            TestDictSchema,
            ExportTestTarget,
            ExportTestTargetSlave,
            ExportTest,
            ExportTestTarget2,
            ExportTestTargetSlave2,
            ExportTestRelation,
            O2MDeletionMaster,
            O2MDeletionChild,
            TestHistoryTable,
            TestHistoryChildTable,
            TestLoaderUpdater,
            module='coog_core', type_='model')

    Pool.register(
        ImportWizard,
        Add2ExportPackageWizard,
        TestCaseWizard,
        ExportFieldsSelection,
        ExportToFile,
        TranslationOverride,
        RevisionBlameWizard,
        wizard_context.PersistentContextWizard,
        module='coog_core', type_='wizard')

    Pool.register_post_init_hooks(cache_fields_get, module='ir')
    Pool.register_post_init_hooks(event_process_buttons, module='process')


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
