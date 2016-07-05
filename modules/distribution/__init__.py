# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .distribution import *
from .res import *
from .test_case import *
from .party import *
from .configuration import *


def register():
    Pool.register(
        DistributionNetwork,
        Party,
        DistributionNetworkContactMechanism,
        User,
        TestCaseModel,
        Configuration,
        module='distribution', type_='model')
