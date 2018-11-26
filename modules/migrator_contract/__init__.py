from trytond.pool import Pool

from . import contract


def register():
    Pool.register(
        contract.MigratorContract,
        contract.MigratorContractVersion,
        contract.MigratorContractOption,
        contract.MigratorContractEvent,
        contract.MigratorContractPremium,
        contract.MigratorContractWaiverPremium,
        module='migrator_contract', type_='model')
