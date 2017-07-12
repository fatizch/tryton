# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import journal
import move
import statement
import test_case
import wizard
import party


def register():
    Pool.register(
        statement.Line,
        statement.Statement,
        statement.LineGroup,
        test_case.TestCaseModel,
        journal.Journal,
        move.Move,
        move.MoveLine,
        statement.CancelLineGroupStart,
        journal.CancelMotive,
        journal.JournalCancelMotiveRelation,
        wizard.PaymentInformations,
        wizard.StartCreateStatement,
        module='account_statement_cog', type_='model')
    Pool.register(
        statement.CancelLineGroup,
        wizard.CreateStatement,
        party.PartyReplace,
        module='account_statement_cog', type_='wizard')
