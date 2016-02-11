from trytond.pool import Pool
from .test_case import *
from .party import *
from .invoice import *
from .report_engine import *
from .move import *
from .configuration import *
from .payment_term import *


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
        module='account_invoice_cog', type_='model')
