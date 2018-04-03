# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import contract
import invoice
import move
import payment
import event
import offered


def register():
    Pool.register(
        contract.Contract,
        contract.ContractBillingInformation,
        invoice.Invoice,
        move.MoveLine,
        payment.Mandate,
        payment.Payment,
        payment.Journal,
        payment.JournalFailureAction,
        payment.PaymentCreationStart,
        event.EventLog,
        payment.MergedPaymentsByContracts,
        offered.Product,
        module='account_payment_sepa_contract', type_='model')
