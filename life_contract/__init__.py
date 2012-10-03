from trytond.pool import Pool
from .life_contract import *


def register():
    Pool.register(
        # from life_contract
        Contract,
        ExtensionLife,
        CoveredPerson,
        LifeCoveredData,
        LifeCoveredDataDesc,
        LifeCoveredPersonDesc,
        ExtensionLifeState,
        module='life_contract', type_='model')

    Pool.register(
        SubscriptionProcess,
        module='life_contract', type_='wizard')
