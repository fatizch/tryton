from trytond.pool import Pool
from .statement import *
from .test_case import *


def register():
    Pool.register(
        Line,
        # Test Case
        TestCaseModel,
        module='account_statement_cog', type_='model')
