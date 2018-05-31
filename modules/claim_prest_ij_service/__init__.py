# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import claim
import benefit
import wizard
import batch
import configuration


def register():
    Pool.register(
        claim.ClaimIjSubscriptionRequestGroup,
        claim.ClaimIjSubscriptionRequest,
        claim.ClaimIjSubscription,
        benefit.Benefit,
        configuration.ClaimConfiguration,
        batch.CreatePrestIjSubscription,
        batch.SubmitPrestIjSubscription,
        batch.ProcessPrestIjRequest,
        batch.ProcessGestipFluxBatch,
        module='claim_prest_ij_service', type_='model')
    Pool.register(
        wizard.FindPartySubscription,
        wizard.RelaunchPartySubscription,
        module='claim_prest_ij_service', type_='wizard')
