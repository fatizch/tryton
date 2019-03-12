# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import endorsement
from . import process
from . import wizard
from . import document


def register():
    Pool.register(
        process.Process,
        endorsement.Endorsement,
        wizard.EndorsementFindProcess,
        endorsement.EndorsementPartUnion,
        process.Contract,
        wizard.AskNextEndorsementChoice,
        module='endorsement_process', type_='model')
    Pool.register(
        wizard.StartEndorsement,
        wizard.EndorsementStartProcess,
        wizard.PreviewChangesWizard,
        document.ReceiveDocument,
        wizard.AskNextEndorsement,
        module='endorsement_process', type_='wizard')
    Pool.register(
        document.DocumentDescription,
        module='endorsement_process', type_='model',
        depends=['document'])
