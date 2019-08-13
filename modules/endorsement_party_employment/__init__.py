# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import offered
from . import wizard
from . import endorsement


def register():
    Pool.register(
        offered.EndorsementPartyEmploymentField,
        offered.EndorsementPartyEmploymentVersionField,
        endorsement.EndorsementPartyEmployment,
        endorsement.EndorsementPartyEmploymentVersion,
        endorsement.Employment,
        endorsement.EmploymentVersion,
        endorsement.EndorsementParty,
        wizard.ManagePartyEmployment,
        module='endorsement_party_employment', type_='model')

    Pool.register(
        wizard.StartEndorsement,
        module='endorsement_party_employment', type_='wizard')
