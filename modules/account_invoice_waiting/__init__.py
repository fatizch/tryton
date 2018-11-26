# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account
from . import invoice
from . import move


def register():
    Pool.register(
        account.Account,
        move.Move,
        invoice.Invoice,
        module='account_invoice_waiting', type_='model')
