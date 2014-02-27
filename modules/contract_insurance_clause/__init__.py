from trytond.pool import Pool
from .clause import *
from .contract import *


def register():
    Pool.register(
        # From file clause
        ContractClause,
        # From file contract
        Contract,
        CoveredData,
        module='contract_insurance_clause', type_='model')
