from trytond.pool import Pool
from .offered import *
from .endorsement import *
from .wizard import *


def register():
    Pool.register(
        EndorsementPart,
        Contract,
        Endorsement,
        ChangeContractCommission,
        ChangeContractBroker,
        module='endorsement_commission', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_commission', type_='wizard')
