from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        Contract,
        ContractOption,
        Beneficiary,
        module='contract_life_clause', type_='model')
