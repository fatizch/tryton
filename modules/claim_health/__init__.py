# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import claim
from . import contract
from . import wizard
from . import benefit
from . import party


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
        module='claim_health', type_='model')
    Pool.register(
        party.PartyReplace,
        module='claim_health', type_='wizard')
    Pool.register(
        wizard.ModifyCoveredElement,
        wizard.CoveredElementDisplayer,
        wizard.ChangeContractSubscriber,
        module='claim_health', type_='model',
        depends=['endorsement_insurance'])
