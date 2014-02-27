from trytond.pool import Pool
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


def register():
    Pool.register(
        # From export
        ExportPackage,
        ExportInstance,
        # From ir
        Sequence,
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
        # From res
        Group,
        User,
        ResUserWarning,
        # From model
        FileSelector,
        VersionedObject,
        VersionObject,
        # From view_validation_batch
        ViewValidationBatch,
        # From test_case_framework
        TestCaseModel,
        TestCaseSelector,
        SelectTestCase,
        TestCaseFileSelector,
        module='cog_utils', type_='model')
    Pool.register(
        # From export
        ImportWizard,
        # From test_case_framework
        TestCaseWizard,
        module='cog_utils', type_='wizard')
