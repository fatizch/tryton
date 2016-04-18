from trytond.pool import Pool
from trytond.config import config

from .batch import *
from .utils import *
from .coop_date import *
from .coop_string import *
from .export import *
from .ir import *
from .res import *
from .model import *
from .many2one_form import *
from .business import *
from .test_case_framework import *
from .models_for_tests import *
from .tag import *
from .event import *
from .attachment import *
from .diff_blame import *
from .note import *

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
        VersionedObject,
        VersionObject,
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
        module='cog_utils', type_='model')

    if config.get('env', 'testing') == 'True':
        Pool.register(
            TestDictSchema,
            ExportTestTarget,
            ExportTestTargetSlave,
            ExportTest,
            ExportTestTarget2,
            ExportTestTargetSlave2,
            ExportTestRelation,
            O2MDeletionMaster,
            O2MDeletionChild,
            TestVersionedObject,
            TestVersion,
            TestVersion1,
            TestHistoryTable,
            TestHistoryChildTable,
            TestLoaderUpdater,
            module='cog_utils', type_='model')

    Pool.register(
        ImportWizard,
        Add2ExportPackageWizard,
        TestCaseWizard,
        ExportFieldsSelection,
        ExportToFile,
        TranslationOverride,
        RevisionBlameWizard,
        module='cog_utils', type_='wizard')
