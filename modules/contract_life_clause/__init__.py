from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        ContractOption,
        Beneficiary,
        module='contract_life_clause', type_='model')
