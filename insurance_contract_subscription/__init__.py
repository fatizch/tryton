from trytond.pool import Pool
from subscription_process import *


def register():
    Pool.register(
        Contract,
        Option,
        CoveredElement,
        CoveredData,
        module='insurance_contract_subscription', type_='model')
