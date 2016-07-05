# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .contract import *
from .loan import *


def register():
    Pool.register(
        Contract,
        Loan,
        module='loan_apr_fr', type_='model')
