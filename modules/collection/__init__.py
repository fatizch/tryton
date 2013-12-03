from trytond.pool import Pool
from .collection import *
from .test_case import *


def register():
    Pool.register(
        # From collection
        SuspenseParty,
        Configuration,
        Collection,
        Payment,
        CollectionParameters,
        Assignment,
        AssignCollection,
        # From test_case
        TestCaseModel,
        module='collection', type_='model')

    Pool.register(
        # From collection
        CollectionWizard,
        module='collection', type_='wizard')
