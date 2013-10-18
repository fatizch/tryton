from trytond.pool import Pool
from .life_contract import *


def register():
    Pool.register(
        # from life_contract
        Contract,
        LifeOption,
        LifeCoveredData,
        PriceLine,
        module='life_contract', type_='model')
