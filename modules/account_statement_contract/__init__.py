from trytond.pool import Pool
from .statement import *


def register():
    Pool.register(
        Line,
        module='account_statement_contract', type_='model')
    Pool.register(
        BankDepositTicketReport,
        module='account_statement_contract', type_='report')
