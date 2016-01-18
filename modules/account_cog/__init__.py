from trytond.pool import Pool

from .account import *
from .company import *
from .tax import *
from .test_case import *
from .party import *
from .move import *


def register():
    Pool.register(
        MoveTemplate,
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
        Company,
        Tax,
        TaxTemplate,
        TaxCodeTemplate,
        TaxCode,
        TaxGroup,
        TestCaseModel,
        Party,
        SynthesisMenuMoveLine,
        SynthesisMenu,
        OpenThirdPartyBalanceStart,
        module='account_cog', type_='model')
    Pool.register(
        SynthesisMenuOpen,
        OpenThirdPartyBalance,
        CreateMove,
        module='account_cog', type_='wizard')
    Pool.register(
        ThirdPartyBalance,
        module='account', type_='report')
