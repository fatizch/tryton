from trytond.pool import Pool

from .payment import *
from .configuration import *


def register():
    Pool.register(
        Configuration,
        PartyJournalRelation,
        module='account_payment_extended_conf', type_='model')
