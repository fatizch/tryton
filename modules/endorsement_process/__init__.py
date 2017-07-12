# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import endorsement
import process
import wizard
import document


def register():
    Pool.register(
        process.Process,
        endorsement.Endorsement,
        wizard.EndorsementFindProcess,
        endorsement.EndorsementPartUnion,
        process.Contract,
        document.DocumentDescription,
        module='endorsement_process', type_='model')
    Pool.register(
        wizard.StartEndorsement,
        wizard.EndorsementStartProcess,
        wizard.PreviewChangesWizard,
        document.ReceiveDocument,
        module='endorsement_process', type_='wizard')
