from trytond.pool import Pool
from .test_case import *
from .party import *
from .invoice import *
from .report_engine import *


def register():
    Pool.register(
        Invoice,
        TestCaseModel,
        Party,
        ReportTemplate,
        module='account_invoice_cog', type_='model')
