from trytond.pool import Pool

from .dunning import *
from .batch import *


def register():
    Pool.register(
        Dunning,
        Level,
        Procedure,
        DunningCreationBatch,
        DunningTreatmentBatch,
        module='account_dunning_cog', type_='model')
