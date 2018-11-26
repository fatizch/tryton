# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import payment
from . import configuration
from . import offered
from . import move
from . import event
from . import contract
from . import report


def register():
    Pool.register(
        payment.Payment,
        payment.Journal,
        payment.JournalFailureAction,
        payment.MergedPaymentsByContracts,
        payment.PaymentCreationStart,
        configuration.Configuration,
        offered.Product,
        offered.BillingMode,
        move.MoveLine,
        contract.Contract,
        report.ReportTemplate,
        module='contract_insurance_payment', type_='model')
    Pool.register(
        payment.PaymentCreation,
        module='contract_insurance_payment', type_='wizard')
    Pool.register(
        event.EventLog,
        module='contract_insurance_payment', type_='model',
        depends=['event_log'])
