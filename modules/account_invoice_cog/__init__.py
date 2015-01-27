from trytond.pool import Pool
from .test_case import *
from .party import *
from .invoice import *


def register():
    Pool.register(
        Invoice,
        TestCaseModel,
        Party,
        module='account_invoice_cog', type_='model')
