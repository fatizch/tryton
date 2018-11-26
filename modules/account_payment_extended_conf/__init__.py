# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import payment
from . import configuration
from . import party


def register():
    Pool.register(
        configuration.Configuration,
        payment.PartyJournalRelation,
        module='account_payment_extended_conf', type_='model')
    Pool.register(
        party.PartyReplace,
        module='account_payment_extended_conf', type_='wizard')
