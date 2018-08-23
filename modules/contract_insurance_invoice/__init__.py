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
import wizard


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
        batch.BulkSetNumberInvoiceContractBatch,
        batch.RebillBatch,
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
        event.EventTypeAction,
        invoice.Invoice,
        invoice.InvoiceLine,
        invoice.InvoiceTax,
        invoice.InvoiceLineAggregatesDisplay,
        invoice.InvoiceLineAggregatesDisplayLine,
        invoice.InvoiceLineDetail,
        move.Move,
        move.MoveLine,
        move.ReconcileShow,
        move.Reconciliation,
        party.SynthesisMenu,
        party.SynthesisMenuInvoice,
        party.Party,
        payment.JournalFailureAction,
        payment.Payment,
        payment.PaymentSuspension,
        payment.Journal,
        rule_engine.RuleEngineRuntime,
        module='contract_insurance_invoice', type_='model')
    Pool.register(
        wizard.CreateStatement,
        contract.DisplayContractPremium,
        contract.InvoiceContract,
        invoice.InvoiceLineAggregates,
        move.Reconcile,
        party.SynthesisMenuOpen,
        party.PartyReplace,
        wizard.PartyErase,
        module='contract_insurance_invoice', type_='wizard')
    Pool.register(
        event.EventLog,
        module='contract_insurance_invoice', type_='model',
        depends=['event_log'])
    Pool.register(
        batch.RenewContracts,
        module='contract_insurance_invoice', type_='model',
        depends=['contract_term_renewal'])
