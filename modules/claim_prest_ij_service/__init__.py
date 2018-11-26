# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import claim
from . import benefit
from . import wizard
from . import batch
from . import process
from . import rule_engine
from . import configuration


def register():
    Pool.register(
        claim.ClaimIjSubscription,
        claim.ClaimIjSubscriptionRequestGroup,
        claim.ClaimIjSubscriptionRequest,
        claim.ClaimService,
        claim.ClaimIndemnification,
        claim.ClaimIjPeriod,
        claim.ClaimIjPeriodLine,
        process.Process,
        benefit.Benefit,
        benefit.EventDesc,
        wizard.CoveredPersonIjSubscriptionSelectDate,
        wizard.TreatIjPeriodSelect,
        wizard.TreatIjPeriodSelectLine,
        wizard.IndemnificationDefinition,
        configuration.ClaimConfiguration,
        rule_engine.RuleRuntime,
        batch.CreatePrestIjSubscription,
        batch.SubmitPersonPrestIjSubscription,
        batch.SubmitCompanyPrestIjSubscription,
        batch.ProcessPrestIjRequest,
        batch.ProcessGestipFluxBatch,
        batch.CreatePrestIjPeriodsBatch,
        module='claim_prest_ij_service', type_='model')
    Pool.register(
        wizard.FindPartySubscription,
        wizard.CreateCoveredPersonIjSubscription,
        wizard.RelaunchPartySubscription,
        wizard.TreatIjPeriod,
        wizard.CreateIndemnification,
        wizard.PartyErase,
        module='claim_prest_ij_service', type_='wizard')
