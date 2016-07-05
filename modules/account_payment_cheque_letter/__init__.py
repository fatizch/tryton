# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .payment import *
from .report import *
from .report_engine import *


def register():
    Pool.register(
        Payment,
        MergedPayments,
        Journal,
        Group,
        ProcessPaymentStart,
        ReportTemplate,
        module='account_payment_cheque_letter', type_='model')
    Pool.register(
        ProcessPayment,
        module='account_payment_cheque_letter', type_='wizard')
    Pool.register(
        ReportGenerate,
        module='account_payment_cheque_letter', type_='report')
