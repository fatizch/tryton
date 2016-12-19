# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.config import config

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
from .hardware_bench import *
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
        BenchmarkClass,
        Model,
        ModelField,
        UIMenuAccess,
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
