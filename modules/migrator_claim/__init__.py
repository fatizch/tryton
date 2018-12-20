# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import claim


def register():
    Pool.register(
        claim.MigratorClaim,
        claim.MigratorClaimIndemnification,
        module='migrator_claim', type_='model')
