# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .party import *
from .address import *


def register():
    Pool.register(
        MigratorCountry,
        MigratorParty,
        MigratorAddress,
        MigratorContact,
        MigratorZip,
        MigratorPartyRelation,
        module='migrator_party', type_='model')
