from trytond.pool import Pool
from .collection import *


def register():
    Pool.register(
        # from collection
        Company,
        Collection,
        CollectionParameters,
        Assignment,
        AssignCollection,
        module='collection', type_='model')

    Pool.register(
        # from collection
        CollectionWizard,
        module='collection', type_='wizard')
