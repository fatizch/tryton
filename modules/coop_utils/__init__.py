from trytond.pool import Pool
from .utils import *
from .coop_date import *
from .coop_string import *
from .export import *
from .model import *
from .many2one_form import *
from .business import *
from .session import *
from .test_framework import *
from .batchs import *
from .test_case_framework import *


def register():
    Pool.register(
        # from export
        ExportPackage,
        ExportInstance,
        Group,
        UIMenu,
        RuleGroup,
        Action,
        IrModel,
        ModelAccess,
        # from model
        FileSelector,
        TableOfTable,
        DynamicSelection,
        VersionedObject,
        VersionObject,
        # from session
        DateClass,
        # from test_case_framework
        TestCaseModel,
        TestCaseSelector,
        SelectTestCase,
        TestCaseFileSelector,
        module='coop_utils', type_='model')
    Pool.register(
        # from export
        ImportWizard,
        # from test_case_framework
        TestCaseWizard,
        module='coop_utils', type_='wizard')

    add_export_to_model([
            ('ir.model.field', ('name', 'model.model')),
            ('ir.model.field.access', ('field.name', 'field.model.model')),
            ('ir.sequence', ('code', 'name')),
            ('res.user', ('login',)),
            ('ir.action.keyword', ('keyword',)),
            ('res.user.warning', ('name', 'user')),
            ('ir.rule', ('domain',)),
            ('ir.ui.view', ('module', 'type', 'name')),
            ('ir.lang', ('code',)),
            ], 'coop_utils')
