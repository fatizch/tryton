# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import account
import company
import tax
import test_case
import party
import move


def register():
    Pool.register(
        move.MoveTemplate,
        move.Move,
        move.Line,
        move.ReconcileShow,
        move.ReconcileLinesWriteOff,
        account.Account,
        account.AccountTemplate,
        account.AccountTypeTemplate,
        account.AccountKind,
        account.Journal,
        account.FiscalYear,
        account.Period,
        account.Configuration,
        company.Company,
        tax.Tax,
        tax.TaxTemplate,
        tax.TaxCodeTemplate,
        tax.TaxCode,
        tax.TaxGroup,
        test_case.TestCaseModel,
        party.Party,
        party.SynthesisMenuMoveLine,
        party.SynthesisMenu,
        account.OpenThirdPartyBalanceStart,
        module='account_cog', type_='model')
    Pool.register(
        move.Reconcile,
        move.ReconcileLines,
        party.SynthesisMenuOpen,
        account.OpenThirdPartyBalance,
        move.CreateMove,
        module='account_cog', type_='wizard')
    Pool.register(
        account.ThirdPartyBalance,
        module='account', type_='report')
