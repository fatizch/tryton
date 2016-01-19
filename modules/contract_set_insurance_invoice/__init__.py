from trytond.pool import Pool
from .contract import *
from .account import *
from .wizard import *
from .dunning import *


def register():
    Pool.register(
        Contract,
        ContractSet,
        Fee,
        Level,
        module='contract_set_insurance_invoice', type_='model')
    Pool.register(
        DisplayContractSetPremium,
        Renew,
        module='contract_set_insurance_invoice', type_='wizard')
