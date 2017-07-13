# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import endorsement
import offered
import wizard


def register():
    Pool.register(
        endorsement.HealthComplement,
        endorsement.EndorsementParty,
        offered.EndorsementHealthComplementField,
        endorsement.EndorsementPartyHealthComplement,
        wizard.ChangePartyHealthComplement,
        module='endorsement_party_health_fr', type_='model')

    Pool.register(
        wizard.StartEndorsement,
        module='endorsement_party_health_fr', type_='wizard')
