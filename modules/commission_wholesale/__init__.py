from trytond.pool import Pool
from .commission import *


def register():
    Pool.register(
        Commission,
        Agent,
        module='commission_wholesale', type_='model')
    Pool.register(
        CreateInvoicePrincipal,
        module='commission_wholesale', type_='wizard')
