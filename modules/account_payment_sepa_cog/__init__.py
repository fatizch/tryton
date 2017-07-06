# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import batch
import payment
import bank
import test_case
import account
import party
import move


def register():
    Pool.register(
        party.Party,
        batch.PaymentTreatmentBatch,
        batch.PaymentSepaDoBatch,
        batch.PaymentFailBatch,
        batch.PaymentFailMessageCreationBatch,
        payment.Payment,
        payment.Mandate,
        payment.Group,
        bank.Bank,
        bank.BankAccount,
        bank.BankAccountNumber,
        payment.InvoiceLine,
        payment.Journal,
        test_case.TestCaseModel,
        account.Configuration,
        payment.Message,
        payment.PaymentCreationStart,
        move.MoveLine,
        payment.MergedPayments,
        batch.PaymentGroupCreationBatch,
        batch.PaymentGroupProcessBatch,
        batch.PaymentJournalUpdateSepa,
        module='account_payment_sepa_cog', type_='model')
    Pool.register(
        payment.PaymentCreation,
        module='account_payment_sepa_cog', type_='wizard')
