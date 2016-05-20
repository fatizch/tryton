from trytond.pool import Pool

from .dunning import *
from .offered import *
from .contract import *
from .account import *
from .event import *
from .invoice import *


def register():
    Pool.register(
        Dunning,
        Procedure,
        Level,
        Contract,
        Product,
        MoveLine,
        EventLog,
        Invoice,
        module='contract_insurance_invoice_dunning', type_='model')
