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


def register():
    Pool.register(
        # from export
        ExportPackage,
        ExportInstance,
        Group,
        UIMenu,
        # from model
        FileSelector,
        TableOfTable,
        DynamicSelection,
        VersionedObject,
        VersionObject,
        # from session
        DateClass,
        module='coop_utils', type_='model')
    Pool.register(
        # from export
        ImportWizard,
        module='coop_utils', type_='wizard')

    add_export_to_model([
            ('ir.model', ('model',)),
            ('ir.model.field', ('name', 'model.model')),
            ('res.group', ('name',)),
            ('ir.ui.menu', ('name',)),
            ('ir.model.field.access', ('field.name', 'field.model.model')),
            ('ir.rule.group', ('name',)),
            ('ir.sequence', ('code', 'name')),
            ('res.user', ('login',)),
            ('ir.action', ('type', 'name')),
            ('ir.action.keyword', ('keyword',)),
            ('res.user.warning', ('name', 'user')),
            ('ir.rule', ('domain',)),
            ('ir.model.access', ('group.name', 'model.model')),
            ('ir.ui.view', ('module', 'type', 'name')),
            ('ir.lang', ('code',)),
            ('currency.currency', ('code',)),
            ('currency.currency.rate', ()),
            ], 'coop_utils')
