from trytond.pool import Pool
from .life_contract import *


def register():
    Pool.register(
        # from life_contract
        Contract,
        CoveredPerson,
        LifeCoveredData,
        LifeCoveredDesc,
        ExtensionLifeState,
        PriceLine,
        module='life_contract', type_='model')

    Pool.register(
        SubscriptionProcess,
        module='life_contract', type_='wizard')
