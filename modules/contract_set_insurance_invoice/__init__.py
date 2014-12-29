from trytond.pool import Pool
from .contract import *
from .account import *


def register():
    Pool.register(
        Contract,
        ContractSet,
        Fee,
        module='contract_set_insurance_invoice', type_='model')
    Pool.register(
        DisplayContractSetPremium,
        module='contract_set_insurance_invoice', type_='wizard')
