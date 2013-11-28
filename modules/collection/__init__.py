from trytond.pool import Pool
from .collection import *
from .test_case import *


def register():
    Pool.register(
        # from collection
        SuspenseParty,
        Configuration,
        Collection,
        Payment,
        CollectionParameters,
        Assignment,
        AssignCollection,
        # TODO : Move in utils.export
        Property,
        # from test_case
        TestCaseModel,
        module='collection', type_='model')

    Pool.register(
        # from collection
        CollectionWizard,
        module='collection', type_='wizard')
