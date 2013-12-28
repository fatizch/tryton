from trytond.pool import Pool
from .address import *
from .party import *
from .test_case import *


def register():
    Pool.register(
        # from address
        Address,
        # from party
        Party,
        # from test_case
        TestCaseModel,
        module='coop_party_fr', type_='model')
