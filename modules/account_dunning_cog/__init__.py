# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import batch
from . import dunning
from . import event
from . import party
from . import account


def register():
    Pool.register(
        dunning.Dunning,
        dunning.Level,
        dunning.Procedure,
        batch.DunningUpdateBatch,
        batch.DunningCreationBatch,
        batch.DunningTreatmentBatch,
        party.Party,
        party.PartyDunningProcedure,
        account.Configuration,
        account.ConfigurationDefaultDunningProcedure,
        account.MoveLine,
        module='account_dunning_cog', type_='model')
    Pool.register(
        event.EventLog,
        module='account_dunning_cog', type_='model',
        depends=['event_log'])
