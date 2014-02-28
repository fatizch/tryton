from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        # From file contract
        Beneficiary,
        ContractClause,
        CoveredData,
        module='contract_life_clause', type_='model')
