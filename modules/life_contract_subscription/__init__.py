from trytond.pool import Pool

from .life_contract_subscription import *

def register():
    Pool.register(
        # from life_contract_subscription
        CoveredPersonSubs,
        CoveredDataSubs,
        module='life_contract_subscription', type_='model')

