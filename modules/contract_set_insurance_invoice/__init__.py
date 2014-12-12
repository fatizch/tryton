from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        Contract,
        ContractSet,
        module='contract_set_insurance_invoice', type_='model')
    Pool.register(
        DisplayContractSetPremium,
        module='contract_set_insurance_invoice', type_='wizard')
