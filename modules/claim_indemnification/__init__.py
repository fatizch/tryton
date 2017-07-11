# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import batch
import benefit
import configuration
import claim
import rule_engine
import invoice
import event
import move
import party
import wizard
from trytond.pool import Pool
from benefit import BenefitRule  # NOQA


def register():
    Pool.register(
        party.InsurerDelegation,
        benefit.Benefit,
        benefit.BenefitProduct,
        benefit.BenefitRule,
        claim.Claim,
        claim.Loss,
        claim.ClaimService,
        claim.Indemnification,
        claim.IndemnificationDetail,
        invoice.Invoice,
        invoice.InvoiceLine,
        invoice.ClaimInvoiceLineDetail,
        rule_engine.RuleEngine,
        rule_engine.RuleEngineRuntime,
        event.EventLog,
        wizard.ExtraDataValueDisplayer,
        wizard.ExtraDatasDisplayers,
        wizard.SelectService,
        wizard.IndemnificationDefinition,
        wizard.IndemnificationCalculationResult,
        wizard.IndemnificationRegularisation,
        wizard.IndemnificationAssistantView,
        wizard.IndemnificationValidateElement,
        wizard.IndemnificationControlElement,
        claim.IndemnificationControlRule,
        configuration.Configuration,
        event.EventTypeAction,
        batch.CreateClaimIndemnificationBatch,
        move.MoveLine,
        module='claim_indemnification', type_='model')
    Pool.register(
        wizard.FillExtraData,
        wizard.CreateIndemnification,
        wizard.IndemnificationAssistant,
        party.PartyReplace,
        module='claim_indemnification', type_='wizard')
