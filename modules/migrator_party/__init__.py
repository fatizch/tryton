# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import party
import address


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
