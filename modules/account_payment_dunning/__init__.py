from trytond.pool import Pool
from .payment import *


def register():
    Pool.register(
        PaymentJournal,
        JournalFailureAction,
        JournalFailureDunning,
        Payment,
        module='account_payment_dunning', type_='model')
