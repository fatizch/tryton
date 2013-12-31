from trytond.pool import Pool

from .subscription_process import *
from .contract import *


def register():
    Pool.register(
        Contract,
        ContractOption,
        CoveredElement,
        CoveredData,
        Process,
        ContractSubscribeFindProcess,
        module='insurance_contract_subscription', type_='model')

    Pool.register(
        ContractSubscribe,
        module='insurance_contract_subscription', type_='wizard')
