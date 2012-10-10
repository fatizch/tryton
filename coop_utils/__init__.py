from trytond.pool import Pool
from .utils import *
from .date import *
from .string import *
from .model import *
from .many2one_form import *
from .business import *
from .session import *


def register():
    Pool.register(
        # from model
        TableOfTable,
        DynamicSelection,
        # from session
        DateClass,
        module='coop_utils', type_='model')
