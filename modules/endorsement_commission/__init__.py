# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import offered
import endorsement
import wizard


def register():
    Pool.register(
        offered.EndorsementPart,
        endorsement.Contract,
        endorsement.Endorsement,
        wizard.ChangeContractCommission,
        wizard.ChangeContractBroker,
        module='endorsement_commission', type_='model')

    Pool.register(
        wizard.StartEndorsement,
        module='endorsement_commission', type_='wizard')
