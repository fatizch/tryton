# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import batch
import invoice
import party
import offered
import contract
import account
import move
import rule_engine
import event
import bank
import configuration
import payment


def register():
    Pool.register(
        account.Configuration,
        account.Fee,
        bank.BankAccount,
        batch.CreateInvoiceContractBatch,
        batch.InvoiceAgainstBalanceBatch,
        batch.PostInvoiceAgainstBalanceBatch,
        batch.PostInvoiceContractBatch,
        batch.SetNumberInvoiceAgainstBalanceBatch,
        batch.SetNumberInvoiceContractBatch,
        configuration.OfferedConfiguration,
        offered.BillingMode,
        offered.BillingModeFeeRelation,
        offered.BillingModePaymentTermRelation,
        offered.OptionDescription,
        offered.OptionDescriptionPremiumRule,
        offered.PaymentTerm,
        offered.PaymentTermLine,
        offered.PaymentTermLineRelativeDelta,
        offered.Product,
        offered.ProductBillingModeRelation,
        contract.Contract,
        contract.ContractBillingInformation,
        contract.ContractFee,
        contract.ContractInvoice,
        contract.ContractOption,
        contract.ContractSubStatus,
        contract.ExtraPremium,
        contract.InvoiceContractStart,
        contract.Premium,
        event.Event,
        event.EventLog,
        event.EventTypeAction,
        invoice.Invoice,
        invoice.InvoiceLine,
        invoice.InvoiceLineAggregatesDisplay,
        invoice.InvoiceLineAggregatesDisplayLine,
        invoice.InvoiceLineDetail,
        move.Move,
        move.MoveLine,
        move.ReconcileShow,
        party.SynthesisMenu,
        party.SynthesisMenuInvoice,
        payment.JournalFailureAction,
        payment.Payment,
        payment.PaymentSuspension,
        rule_engine.RuleEngineRuntime,
        module='contract_insurance_invoice', type_='model')
    Pool.register(
        contract.DisplayContractPremium,
        contract.InvoiceContract,
        invoice.InvoiceLineAggregates,
        move.Reconcile,
        party.SynthesisMenuOpen,
        party.PartyReplace,
        module='contract_insurance_invoice', type_='wizard')
