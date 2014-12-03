from trytond.pool import Pool
from .test_case import *
from .party import *


def register():
    Pool.register(
        TestCaseModel,
        Party,
        module='account_invoice_cog', type_='model')
