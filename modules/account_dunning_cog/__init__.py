# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .dunning import *
from .batch import *
from .party import *
from .event import *


def register():
    Pool.register(
        Dunning,
        Level,
        Procedure,
        DunningUpdateBatch,
        DunningCreationBatch,
        DunningTreatmentBatch,
        Party,
        EventLog,
        module='account_dunning_cog', type_='model')
