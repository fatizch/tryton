from trytond.pool import Pool

from .dunning import *
from .offered import *
from .contract import *
from .account import *
from .event import *


def register():
    Pool.register(
        Dunning,
        Level,
        Contract,
        Product,
        MoveLine,
        EventLog,
        module='contract_insurance_invoice_dunning', type_='model')
