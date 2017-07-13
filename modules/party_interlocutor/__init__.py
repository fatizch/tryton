# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import interlocutor
import party


def register():
    Pool.register(
        interlocutor.ContactInterlocutor,
        interlocutor.PartyContactInterlocutorPartyContactMechanism,
        module='party_interlocutor', type_='model')
    Pool.register(
        party.PartyReplace,
        module='party_interlocutor', type_='wizard')
