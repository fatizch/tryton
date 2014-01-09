from trytond.pool import Pool
from .collection import *


def register():
    Pool.register(
        # from collection
        CollectionCreateParameters,
        CollectionCreateAssign,
        module='collection_insurance', type_='model')

    Pool.register(
        # from collection
        CollectionCreate,
        module='collection_insurance', type_='wizard')
