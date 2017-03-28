# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.config import config
from trytond.cache import Cache

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
        module='coog_core', type_='wizard')

    Pool.register_post_init_hooks(cache_fields_get, module='ir')


def cache_fields_get(pool):
    from trytond.model import Model

    if hasattr(Model, '_fields_get_cache'):
        return

    Model._fields_get_cache = Cache('fields_get_cache')
    fields_get_orig = Model.fields_get.__func__

    @classmethod
    def patched_fields_get(cls, field_names=None):
        key = (cls.__name__, set(field_names or []))
        cached_value = cls._fields_get_cache.get(key, None)
        if cached_value:
            return cached_value
        res = fields_get_orig(cls, field_names)
        cls._fields_get_cache.set(key, res)
        return res

    Model.fields_get = patched_fields_get
