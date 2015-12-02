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
        DunningCreationBatch,
        DunningTreatmentBatch,
        Party,
        EventLog,
        module='account_dunning_cog', type_='model')
