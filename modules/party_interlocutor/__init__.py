# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .interlocutor import *
import party


def register():
    Pool.register(
        ContactInterlocutor,
        PartyContactInterlocutorPartyContactMechanism,
        module='party_interlocutor', type_='model')
    Pool.register(
        party.PartyReplace,
        module='party_interlocutor', type_='wizard')
