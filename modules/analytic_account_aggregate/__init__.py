# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import account
import batch


def register():
    Pool.register(
        account.Line,
        account.AnalyticLineAggregated,
        batch.ExtractAggregatedMove,
        module='analytic_account_aggregate', type_='model')
    Pool.register(
        account.OpenAnalyticLine,
        module='analytic_account_aggregate', type_='wizard')
