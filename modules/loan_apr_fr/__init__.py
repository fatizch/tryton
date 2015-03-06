from trytond.pool import Pool

from .contract import *
from .loan import *


def register():
    Pool.register(
        Contract,
        Loan,
        module='loan_apr_fr', type_='model')
