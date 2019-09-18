# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import party
from .import contract


def register():
    Pool.register(
        party.MigratorParty,
        contract.MigratorContractHealthOption,
        contract.MigratorContract,
        module='migrator_health', type_='model')
