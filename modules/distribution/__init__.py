from trytond.pool import Pool

from .distribution import *
from .res import *
from .test_case import *
from .party import *


def register():
    Pool.register(
        DistributionNetwork,
        Party,
        DistributionNetworkContactMechanism,
        User,
        TestCaseModel,
        module='distribution', type_='model')
