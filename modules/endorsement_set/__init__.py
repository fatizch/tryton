# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import endorsement
import event


def register():
    Pool.register(
        endorsement.Configuration,
        endorsement.EndorsementSet,
        endorsement.Endorsement,
        endorsement.EndorsementSetSelectDeclineReason,
        event.EventLog,
        event.EventTypeAction,
        module='endorsement_set', type_='model')
    Pool.register(
        endorsement.EndorsementSetDecline,
        module='endorsement_set', type_='wizard')
