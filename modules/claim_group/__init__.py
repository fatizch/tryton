# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import offered
from . import benefit
from . import claim
from . import contract
from . import party


def register():
    Pool.register(
        offered.OptionDescription,
        offered.Product,
        benefit.Benefit,
        claim.Claim,
        claim.ClaimService,
        contract.Contract,
        contract.Option,
        contract.CoveredElement,
        module='claim_group', type_='model')
    Pool.register(
        party.PartyReplace,
        module='claim_group', type_='wizard')
    Pool.register(
        contract.TerminateContract,
        module='claim_group', type_='model',
        depends=['endorsement'])
