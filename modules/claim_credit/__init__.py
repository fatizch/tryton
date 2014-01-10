from trytond.pool import Pool
from .claim import *
from .contract import *


def register():
    Pool.register(
        # From contract
        ContractService,
        # From claim
        ClaimIndemnification,
        module='claim_credit', type_='model')
