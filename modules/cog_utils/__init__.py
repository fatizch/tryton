from trytond.pool import Pool
from trytond.config import config
from .utils import *
from .coop_date import *
from .coop_string import *
from .export import *
from .ir import *
from .res import *
from .model import *
from .many2one_form import *
from .business import *
from .test_framework import *
from .batchs import *
from .view_validation_batch import *
from .test_case_framework import *
from .models_for_tests import *
from .tag import *


def register():
    Pool.register(
        ExportPackage,
        ExportInstance,
        Add2ExportPackageWizardStart,
        Sequence,
        SequenceStrict,
        DateClass,
        View,
        UIMenu,
        Rule,
        RuleGroup,
        Action,
        ActionKeyword,
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
        TestCaseModel,
        TestCaseInstance,
        TestCaseRequirementRelation,
        TestCaseSelector,
        SelectTestCase,
        TestCaseFileSelector,
        Tag,
        TagObjectRelation,
        MethodDefinition,
        module='cog_utils', type_='model')
    if config.get('env', 'testing') == 'True':
        Pool.register(
            ExportTestTarget,
            ExportTestTargetSlave,
            ExportTest,
            ExportTestTarget2,
            ExportTestTargetSlave2,
            ExportTestRelation,
            module='cog_utils', type_='model')
    Pool.register(
        ImportWizard,
        Add2ExportPackageWizard,
        TestCaseWizard,
        module='cog_utils', type_='wizard')
