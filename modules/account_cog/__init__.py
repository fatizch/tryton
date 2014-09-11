from trytond.pool import Pool

from .account import *
from .company import *
from .tax import *
from .fee import *
from .test_case import *
from .party import *
from .move import *


def register():
    Pool.register(
        # From account
        Move,
        Line,
        Account,
        AccountTemplate,
        AccountTypeTemplate,
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
        Tax,
        TaxTemplate,
        TaxCodeTemplate,
        TaxCode,
        TaxGroup,
        # From fee
        FeeDescription,
        FeeDescriptionVersion,
        # From test_case
        TestCaseModel,
        SynthesisMenuMoveLine,
        SynthesisMenu,
        OpenThirdPartyBalanceStart,
        module='account_cog', type_='model')
    Pool.register(
        SynthesisMenuOpen,
        OpenThirdPartyBalance,
        module='account_cog', type_='wizard')
    Pool.register(
        ThirdPartyBalance,
        module='account', type_='report')
