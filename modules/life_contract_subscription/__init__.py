from trytond.pool import Pool

from .contract import *


def register():
    Pool.register(
        # from contract
        Contract,
        CoveredData,
        module='life_contract_subscription', type_='model')
