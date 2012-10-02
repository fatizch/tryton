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
        SessionClass,
        DateClass,
        AskDate,
        module='coop_utils', type_='model')

    Pool.register(
        # from session
        ChangeSessionDate,
        module='coop_utils', type_='wizard')
