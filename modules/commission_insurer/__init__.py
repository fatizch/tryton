# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .commission import *
from .account import *
from .party import *
from .batch import *


def register():
    Pool.register(
        Commission,
        CreateInvoicePrincipalAsk,
        MoveLine,
        InvoiceLine,
        Invoice,
        Insurer,
        CreateEmptyInvoicePrincipalBatch,
        LinkInvoicePrincipalBatch,
        FinalizeInvoicePrincipalBatch,
        module='commission_insurer', type_='model')
    Pool.register(
        CreateInvoicePrincipal,
        module='commission_insurer', type_='wizard')
