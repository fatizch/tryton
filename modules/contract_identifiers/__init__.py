# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import contract


def register():
    Pool.register(
        contract.ContractIdentifierType,
        contract.ContractIdentifier,
        contract.Contract,
        module='contract_identifiers', type_='model')
