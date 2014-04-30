from trytond.pool import Pool
from .clause import *
from .contract import *


def register():
    Pool.register(
        Contract,
        ContractClause,
        module='contract_clause', type_='model')
