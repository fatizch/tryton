from trytond.pool import Pool
from .process import *


def register():
    Pool.register(
        Process,
        EndorsementPartyFindProcess,
        EndorsementFindProcess,
        Party,
        module='endorsement_party_process', type_='model')
    Pool.register(
        EndorsementPartyStartProcess,
        module='endorsement_party_process', type_='wizard')
