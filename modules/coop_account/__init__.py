from trytond.pool import Pool

from .tax import *
from .fee import *
from .test_case import *


def register():
    Pool.register(
        # from tax
        TaxDesc,
        TaxVersion,
        # from fee
        FeeDesc,
        FeeVersion,
        # from test_case
        TestCaseModel,
        module='coop_account', type_='model')
