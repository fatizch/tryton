from trytond.pool import Pool
from .company import *
from .test_case import *


def register():
    Pool.register(
        # From file company
        Company,
        # From file test_case
        TestCaseModel,
        module='coop_company', type_='model')
