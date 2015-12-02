from trytond.pool import Pool
from .test_case import *
from .party import *
from .invoice import *
from .report_engine import *
from .move import *
from .configuration import *


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
        module='account_invoice_cog', type_='model')
