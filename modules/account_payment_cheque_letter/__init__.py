# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import payment
import report
import report_engine


def register():
    Pool.register(
        payment.Payment,
        payment.MergedPayments,
        payment.Journal,
        payment.Group,
        payment.ProcessPaymentStart,
        report.ReportTemplate,
        module='account_payment_cheque_letter', type_='model')
    Pool.register(
        payment.ProcessPayment,
        module='account_payment_cheque_letter', type_='wizard')
    Pool.register(
        report_engine.ReportGenerate,
        module='account_payment_cheque_letter', type_='report')
