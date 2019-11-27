# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import party


def register():
    Pool.register(
        party.MigratorPartyEmployment,
        module='migrator_party_employment', type_='model')
    Pool.register(
        party.MigratorPartyPublicEmployment,
        module='migrator_party_employment', type_='model',
        depends=['party_public_employment'])
    Pool.register(
        party.MigratorPartyPublicEmploymentFr,
        module='migrator_party_employment', type_='model',
        depends=['party_public_employment_fr'])
