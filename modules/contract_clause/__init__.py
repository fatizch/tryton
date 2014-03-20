from trytond.pool import Pool
from .clause import *
from .contract import *


def register():
    Pool.register(
        # From file clause
        ContractClause,
        # From file contract
        Contract,
        module='contract_clause', type_='model')
