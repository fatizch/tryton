# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .endorsement import *
from .process import *
from .wizard import *
from .document import *


def register():
    Pool.register(
        Process,
        Endorsement,
        EndorsementFindProcess,
        EndorsementPartUnion,
        Contract,
        DocumentDescription,
        module='endorsement_process', type_='model')
    Pool.register(
        StartEndorsement,
        EndorsementStartProcess,
        PreviewChangesWizard,
        ReceiveDocument,
        module='endorsement_process', type_='wizard')