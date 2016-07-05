# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .payment import *


def register():
    Pool.register(
        PaymentJournal,
        JournalFailureAction,
        JournalFailureDunning,
        Payment,
        module='account_payment_dunning', type_='model')
