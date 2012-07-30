from trytond.pool import Pool
from .utils import *
from .model import *
from .many2one_form import *
from .one2many_domain import *


def register():
    Pool.register(
        DynamicSelection,
        TableOfTable,
        module='coop_utils', type_='model')
