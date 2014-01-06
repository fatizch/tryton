from trytond.pool import Pool

from .life_contract_subscription import *


def register():
    Pool.register(
        # from life_contract_subscription
        Contract,
        CoveredData,
        module='life_contract_subscription', type_='model')
