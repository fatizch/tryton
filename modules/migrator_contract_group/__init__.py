# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import contract


def register():
    Pool.register(
        contract.MigratorContractGroup,
        contract.MigratorContractSubsidiary,
        contract.MigratorSubsidiaryAffiliated,
        contract.MigratorContractGroupConfiguration,
        module='migrator_contract_group', type_='model')
    Pool.register(
        contract.MigratorContractGroupManagement,
        module='migrator_contract_group', type_='model', depends=[
            'claim_group'])