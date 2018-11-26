# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import contract
from . import invoice
from . import move
from . import payment
from . import event
from . import offered


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
        payment.MergedPaymentsByContracts,
        offered.Product,
        module='account_payment_sepa_contract', type_='model')
    Pool.register(
        event.EventLog,
        module='account_payment_sepa_contract', type_='model',
        depends=['event_log'])
