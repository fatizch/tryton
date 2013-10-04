from trytond.pool import Pool
from .collection import *


def register():
    Pool.register(
        # from collection
        SuspenseParty,
        Configuration,
        Collection,
        CollectionParameters,
        Assignment,
        AssignCollection,
        # TODO : Move in utils.export
        Property,
        module='collection', type_='model')

    Pool.register(
        # from collection
        CollectionWizard,
        module='collection', type_='wizard')
