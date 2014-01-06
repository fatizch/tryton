from trytond.pool import Pool
from .collection import *


def register():
    Pool.register(
        # from collection
        CollectionCreateParameters,
        CollectionCreateAssign,
        module='insurance_collection', type_='model')

    Pool.register(
        # from collection
        CollectionCreate,
        module='insurance_collection', type_='wizard')
