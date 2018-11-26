# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import statement
from . import contract


def register():
    Pool.register(
        statement.Line,
        contract.Contract,
        module='account_statement_contract', type_='model')
    Pool.register(
        statement.BankDepositTicketReport,
        module='account_statement_contract', type_='report')
