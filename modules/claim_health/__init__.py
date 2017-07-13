# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import claim
import contract
import wizard
import benefit
import party


def register():
    Pool.register(
        benefit.LossDescription,
        benefit.MedicalActFamily,
        benefit.MedicalActDescription,
        claim.HealthLoss,
        claim.Loss,
        claim.Claim,
        claim.ClaimService,
        contract.CoveredElement,
        wizard.ModifyCoveredElement,
        wizard.CoveredElementDisplayer,
        wizard.ChangeContractSubscriber,
        module='claim_health', type_='model')
    Pool.register(
        party.PartyReplace,
        module='claim_health', type_='wizard')
