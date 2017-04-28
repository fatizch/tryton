# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import offered
import benefit
import claim
import contract
import party


def register():
    Pool.register(
        offered.OptionDescription,
        benefit.Benefit,
        claim.Claim,
        claim.ClaimService,
        contract.Contract,
        contract.Option,
        contract.CoveredElement,
        contract.TerminateContract,
        module='claim_group', type_='model')
    Pool.register(
        party.PartyReplace,
        module='claim_group', type_='wizard')
