# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import party


def register():
    Pool.register(
        party.EmploymentVersion,
        party.AdminSituationSubStatus,
        party.PublicEmploymentIndex,
        module='party_public_employment', type_='model')
