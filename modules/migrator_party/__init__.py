# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import party
from . import address
from . import party_ssn
from . import party_birth_data


def register():
    Pool.register(
        address.MigratorCountry,
        party.MigratorParty,
        party.MigratorContactMechanism,
        party.MigratorCompany,
        address.MigratorAddress,
        address.MigratorZip,
        party.MigratorPartyRelation,
        module='migrator_party', type_='model')
    Pool.register(
        party.MigratorInterlocutor,
        module='migrator_party', type_='model', depends=['party_interlocutor'])
    Pool.register(
        party_ssn.MigratorParty,
        module='migrator_party', type_='model', depends=['party_ssn'])
    Pool.register(
        party_birth_data.MigratorParty,
        module='migrator_party', type_='model', depends=['party_birth_data']
    )
