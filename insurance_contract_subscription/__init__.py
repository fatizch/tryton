from trytond.pool import Pool
from subscription_process import *


def register():
    Pool.register(
        ContractSubscription,
        Option,
        CoveredElement,
        CoveredData,
        SubscriptionManager,
        module='insurance_contract_subscription', type_='model')
