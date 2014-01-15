from trytond.pool import Pool

from .contract import *


def register():
    Pool.register(
        # from contract
        Contract,
        CoveredData,
        module='contract_life_process', type_='model')
