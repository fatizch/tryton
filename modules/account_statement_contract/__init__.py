# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .statement import *
from .contract import *


def register():
    Pool.register(
        Line,
        Contract,
        module='account_statement_contract', type_='model')
    Pool.register(
        BankDepositTicketReport,
        module='account_statement_contract', type_='report')
