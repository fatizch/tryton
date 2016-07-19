# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .commission import *
from .invoice import *


def register():
    Pool.register(
        Commission,
        Agent,
        Invoice,
        module='commission_wholesale', type_='model')
    Pool.register(
        CreateInvoicePrincipal,
        module='commission_wholesale', type_='wizard')
