# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import process
import wizard


def register():
    Pool.register(
        process.Process,
        wizard.StartFullContractRevision,
        module='endorsement_full_contract_revision', type_='model')

    Pool.register(
        wizard.StartEndorsement,
        module='endorsement_full_contract_revision', type_='wizard')
