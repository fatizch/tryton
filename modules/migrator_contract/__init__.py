from trytond.pool import Pool

from .contract import *


def register():
    Pool.register(
        MigratorContract,
        MigratorContractVersion,
        MigratorContractOption,
        MigratorContractEvent,
        MigratorContractPremium,
        MigratorContractPremiumWaiver,
        module='migrator_contract', type_='model')
