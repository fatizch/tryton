from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        # from contract
        Contract,
        ContractOption,
        CoveredData,
        module='life_contract', type_='model')
