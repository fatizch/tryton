from trytond.pool import Pool

from .account import *
from .company import *
from .tax import *
from .fee import *
from .test_case import *


def register():
    Pool.register(
        # From account
        Move,
        Account,
        AccountKind,
        Journal,
        FiscalYear,
        Period,
        Configuration,
        # From company
        Company,
        # From tax
        TaxDescription,
        TaxDescriptionVersion,
        # From fee
        FeeDescription,
        FeeDescriptionVersion,
        # From test_case
        TestCaseModel,
        module='account_cog', type_='model')
