# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import party
from . import offered
from . import api


def register():
    Pool.register(
        party.Party,
        module='party_birth_data', type_='model')

    Pool.register(
        party.PartyHexaPoste,
        module='party_birth_data', type_='model', depends=['country_hexaposte'])

    Pool.register(
        party.PartySSN,
        module='party_birth_data', type_='model', depends=['party_ssn'])

    Pool.register(
        offered.ItemDescription,
        module='party_birth_data', type_='model', depends=['offered_insurance'])

    Pool.register(
        api.APIParty,
        api.APIProduct,
        module='party_birth_data', type_='model', depends=['api'])
