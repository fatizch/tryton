from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        # from contract
        Contract,
        ContractOption,
        module='contract_life', type_='model')
