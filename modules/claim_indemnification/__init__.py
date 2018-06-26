# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

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
from benefit import BenefitRule
import payment

__all__ = [
    'BenefitRule'
    ]


def register():
    Pool.register(
        party.InsurerDelegation,
        benefit.Benefit,
        benefit.BenefitProduct,
        benefit.BenefitPaymentJournal,
        benefit.BenefitRule,
        claim.Claim,
        claim.Loss,
        claim.ClaimService,
        claim.IndemnificationPaybackReason,
        claim.Indemnification,
        claim.IndemnificationDetail,
        invoice.Invoice,
        invoice.InvoiceLine,
        invoice.ClaimInvoiceLineDetail,
        rule_engine.RuleEngine,
        rule_engine.RuleEngineRuntime,
        wizard.ExtraDataValueDisplayer,
        wizard.ExtraDatasDisplayers,
        wizard.SelectService,
        wizard.IndemnificationDefinition,
        wizard.IndemnificationCalculationResult,
        wizard.IndemnificationRegularisation,
        wizard.IndemnificationAssistantView,
        wizard.IndemnificationValidateElement,
        wizard.IndemnificationControlElement,
        wizard.CancelIndemnificationReason,
        wizard.ScheduleIndemnifications,
        claim.IndemnificationControlRule,
        configuration.Configuration,
        event.EventTypeAction,
        batch.CreateClaimIndemnificationBatch,
        move.MoveLine,
        payment.Payment,
        claim.ClaimSubStatus,
        module='claim_indemnification', type_='model')
    Pool.register(
        wizard.FillExtraData,
        wizard.CreateIndemnification,
        wizard.IndemnificationAssistant,
        wizard.DeleteIndemnification,
        wizard.CancelIndemnification,
        party.PartyReplace,
        payment.PaymentCreation,
        module='claim_indemnification', type_='wizard')
    Pool.register(
        event.EventLog,
        module='claim_indemnification', type_='model',
        depends=['event_log'])
