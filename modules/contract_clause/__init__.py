# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import contract
import clause


def register():
    Pool.register(
        contract.Contract,
        clause.ContractClause,
        module='contract_clause', type_='model')
