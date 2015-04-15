from trytond.pool import Pool

from .dunning import *
from .offered import *
from .contract import *
from .account import *


def register():
    Pool.register(
        Dunning,
        Level,
        Contract,
        Product,
        MoveLine,
        module='contract_insurance_invoice_dunning', type_='model')
