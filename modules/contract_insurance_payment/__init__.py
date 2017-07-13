# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import payment
import configuration
import offered
import move
import event
import contract
import report


def register():
    Pool.register(
        payment.Payment,
        payment.Journal,
        configuration.Configuration,
        offered.Product,
        payment.JournalFailureAction,
        offered.BillingMode,
        move.MoveLine,
        event.EventLog,
        contract.Contract,
        report.ReportTemplate,
        payment.MergedPaymentsByContracts,
        module='contract_insurance_payment', type_='model')
