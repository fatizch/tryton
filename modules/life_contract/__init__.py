from trytond.pool import Pool
from .life_contract import *


def register():
    Pool.register(
        # from life_contract
        Contract,
        LifeOption,
        CoveredPerson,
        LifeCoveredData,
        PriceLine,
        module='life_contract', type_='model')

    # Pool.register(
    #     SubscriptionProcess,
    #     module='life_contract', type_='wizard')
