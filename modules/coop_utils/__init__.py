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
