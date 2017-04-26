# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import statement


def register():
    Pool.register(
        statement.Line,
        statement.Statement,
        statement.PaymentInformations,
        module='account_statement_contract_fr', type_='model')
    Pool.register(
        statement.CreateStatement,
        module='account_statement_contract_fr', type_='wizard')
