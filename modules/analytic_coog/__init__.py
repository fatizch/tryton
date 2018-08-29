# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import account
import invoice
import line
import rule


def register():
    Pool.register(
        account.Account,
        account.AccountDistribution,
        account.AnalyticAccountEntry,
        invoice.InvoiceLine,
        line.Line,
        rule.Rule,
        module='analytic_coog', type_='model')
