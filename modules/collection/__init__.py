from trytond.pool import Pool
from .collection import *
from .test_case import *
from .party import *
from .account import *


def register():
    Pool.register(
        # From collection
        Collection,
        CollectionCreateParameters,
        CollectionCreateAssignLines,
        CollectionCreateAssign,
        # From Account
        Configuration,
        Payment,
        # From Party
        Party,
        # From test_case
        TestCaseModel,
        module='collection', type_='model')

    Pool.register(
        # From collection
        CollectionCreate,
        module='collection', type_='wizard')
