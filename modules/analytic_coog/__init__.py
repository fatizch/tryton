# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import account
from . import invoice
from . import line
from . import rule


def register():
    Pool.register(
        account.Account,
        account.AccountDistribution,
        account.AnalyticAccountEntry,
        account.MoveLine,
        invoice.InvoiceLine,
        line.Line,
        rule.Rule,
        module='analytic_coog', type_='model')
