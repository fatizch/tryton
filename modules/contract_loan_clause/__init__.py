from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        # From file contract
        ContractClause,
        module='contract_loan_clause', type_='model')
