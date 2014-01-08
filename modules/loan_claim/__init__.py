from trytond.pool import Pool
from .loan_claim import *
from .contract import *


def register():
    Pool.register(
        ContractService,
        # From contract
        ClaimIndemnification,
        module='loan_claim', type_='model')
