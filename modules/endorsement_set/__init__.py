# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .endorsement import *
from .event import *


def register():
    Pool.register(
        Configuration,
        EndorsementSet,
        Endorsement,
        EndorsementSetSelectDeclineReason,
        EventLog,
        EventTypeAction,
        module='endorsement_set', type_='model')
    Pool.register(
        EndorsementSetDecline,
        module='endorsement_set', type_='wizard')
