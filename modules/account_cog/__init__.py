# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
        ReconcileShow,
        ReconcileLinesWriteOff,
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
        Reconcile,
        ReconcileLines,
        SynthesisMenuOpen,
        OpenThirdPartyBalance,
        CreateMove,
        module='account_cog', type_='wizard')
    Pool.register(
        ThirdPartyBalance,
        module='account', type_='report')
