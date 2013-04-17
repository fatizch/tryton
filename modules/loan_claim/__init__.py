from trytond.pool import Pool
from .loan_claim import *


def register():
    Pool.register(
        LoanClaimDeliveredService,
        LoanIndemnification,
        module='loan_claim', type_='model')
