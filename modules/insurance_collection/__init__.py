from trytond.pool import Pool
from .collection import *


def register():
    Pool.register(
        # from collection
        MoveLine,
        CollectionParameters,
        AssignCollection,
        module='insurance_collection', type_='model')

    Pool.register(
        # from collection
        CollectionWizard,
        module='insurance_collection', type_='wizard')
