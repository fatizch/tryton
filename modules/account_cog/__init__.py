# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import account
from . import company
from . import tax
from . import test_case
from . import party
from . import move
from . import batch
from . import load_data


def register():
    Pool.register(
        batch.GenerateAgedBalance,
        move.ManualReconciliationPostponementMotive,
        move.ManualReconciliationPostponement,
        move.MoveTemplate,
        move.Move,
        move.Line,
        move.Reconciliation,
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
        party.PartyAccount,
        party.SynthesisMenuMoveLine,
        party.SynthesisMenu,
        account.MoveTemplate,
        account.MoveTemplateKeyword,
        account.MoveLineTemplate,
        account.TaxLineTemplate,
        load_data.FiscalYearSet,
        module='account_cog', type_='model')
    Pool.register(
        move.Reconcile,
        move.ReconcileLines,
        move.CreateMove,
        party.SynthesisMenuOpen,
        load_data.FiscalYearSetWizard,
        module='account_cog', type_='wizard')
    Pool.register(
        account.ThirdPartyBalance,
        module='account_cog', type_='report')
