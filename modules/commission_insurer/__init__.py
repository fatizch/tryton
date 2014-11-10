from trytond.pool import Pool

from .commission import *
from .account import *
from .party import *


def register():
    Pool.register(
        CreateInvoicePrincipalAsk,
        MoveLine,
        InvoiceLine,
        Insurer,
        module='commission_insurer', type_='model')
    Pool.register(
        CreateInvoicePrincipal,
        module='commission_insurer', type_='wizard')
