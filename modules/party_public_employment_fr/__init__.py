# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import party


def register():
    Pool.register(
        party.Party,
        party.Employment,
        party.CSRH,
        party.PayrollService,
        party.PartyWorkSection,
        party.PartyWorkSectionSubdivisionRelation,
        party.PartySalaryDeductionService,
        module='party_public_employment_fr', type_='model')
