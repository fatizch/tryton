from trytond.pool import Pool

from .account import *
from .company import *
from .tax import *
from .fee import *
from .test_case import *


def register():
    Pool.register(
        # From account
        Account,
        AccountKind,
        Journal,
        FiscalYear,
        Period,
        Configuration,
        # From company
        Company,
        # From tax
        TaxDesc,
        TaxVersion,
        # From fee
        FeeDesc,
        FeeVersion,
        # From test_case
        TestCaseModel,
        module='coop_account', type_='model')
