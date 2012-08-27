from trytond.pool import Pool
from .utils import *
from .model import *
from .many2one_form import *
from .one2many_domain import *
from .business import *
from .reference_form import *


def register():
    Pool.register(
        PartyRelation,
        TableOfTable,
        DynamicSelection,
        module='coop_utils', type_='model')
