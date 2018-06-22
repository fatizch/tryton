# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import payment
import statement
import move


def register():
    Pool.register(
        payment.Payment,
        payment.Journal,
        move.Move,
        module='account_payment_clearing_waiting', type_='model')

    Pool.register(
        statement.CancelLineGroup,
        module='account_payment_clearing_waiting', type_='wizard',
        depends=['account_statement_cog'])

    Pool.register(
        statement.StatementJournal,
        module='account_payment_clearing_waiting', type_='model',
        depends=['account_statement_cog'])
