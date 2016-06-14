# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .payment import *
from .statement import *
from .move import *


def register():
    Pool.register(
        Payment,
        Move,
        Journal,
        StatementJournal,
        module='account_payment_clearing_waiting', type_='model')

    Pool.register(
        CancelLineGroup,
        module='account_payment_clearing_waiting', type_='wizard')
