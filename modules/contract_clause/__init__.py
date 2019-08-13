# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import contract
from . import clause
from . import api


def register():
    Pool.register(
        contract.Contract,
        clause.ContractClause,
        module='contract_clause', type_='model')

    Pool.register(
        api.APIContract,
        module='contract_clause', type_='model', depends=['api'])
