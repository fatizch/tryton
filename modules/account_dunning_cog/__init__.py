# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import batch
import dunning
import event
import party
import account


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
        event.EventLog,
        account.MoveLine,
        module='account_dunning_cog', type_='model')
