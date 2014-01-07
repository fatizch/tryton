from trytond.pool import Pool
from .loan_claim import *
from .claim import *


def register():
    Pool.register(
        ContractService,
        # From claim
        ClaimIndemnification,
        module='loan_claim', type_='model')
