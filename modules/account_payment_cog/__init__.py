# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import batch
import party
import company
import move
import report
import invoice
import payment
import wizard


def register():
    Pool.register(
        payment.Journal,
        payment.RejectReason,
        payment.JournalFailureAction,
        payment.Payment,
        payment.MergedPayments,
        payment.PaymentMotive,
        party.SynthesisMenuPayment,
        party.SynthesisMenu,
        company.Company,
        move.Move,
        move.MoveLine,
        move.PaymentInformationSelection,
        payment.PaymentFailInformation,
        batch.PaymentTreatmentBatch,
        batch.PaymentCreationBatch,
        batch.PaymentSucceedBatch,
        batch.PaymentAcknowledgeBatch,
        batch.PaymentGroupCreationBatch,
        batch.PaymentUpdateBatch,
        batch.PaymentGroupProcessBatch,
        payment.Configuration,
        payment.ConfigurationDirectDebitJournal,
        payment.ConfigurationRejectFeeJournal,
        payment.Group,
        party.Party,
        party.PartyPaymentDirectDebit,
        move.PaymentCreationStart,
        report.ReportTemplate,
        module='account_payment_cog', type_='model')
    Pool.register(
        party.SynthesisMenuOpen,
        move.PaymentInformationModification,
        move.PaymentCreation,
        payment.FilterPaymentsPerMergedId,
        payment.ManualPaymentFail,
        payment.ProcessManualFailPament,
        payment.ProcessPayment,
        wizard.PartyErase,
        module='account_payment_cog', type_='wizard')
    Pool.register(
        invoice.Invoice,
        module='account_payment_cog', type_='model',
        depends=['account_invoice'])
