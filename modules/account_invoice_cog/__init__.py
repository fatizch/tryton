# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .test_case import *
from .party import *
from .invoice import *
from .report_engine import *
from .move import *
from .configuration import *
from .payment_term import *
from .wizard import *


def register():
    Pool.register(
        InvoiceLine,
        Invoice,
        TestCaseModel,
        Party,
        PartyInteraction,
        ReportTemplate,
        Move,
        MoveLine,
        Configuration,
        PaymentTerm,
        SelectTerm,
        module='account_invoice_cog', type_='model')

    Pool.register(
        ChangePaymentTerm,
        module='account_invoice_cog', type_='wizard')
