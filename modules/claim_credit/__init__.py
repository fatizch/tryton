from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        # From contract
        ContractService,
        module='claim_credit', type_='model')
