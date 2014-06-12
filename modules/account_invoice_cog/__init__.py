from trytond.pool import Pool
from .test_case import *


def register():
    Pool.register(
        TestCaseModel,
        module='account_invoice_cog', type_='model')
