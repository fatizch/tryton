# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .distribution import *
from .test_case import *
from .party import *


def register():
    Pool.register(
        DistributionNetwork,
        DistributionNetworkContactMechanism,
        Party,
        TestCaseModel,
        module='distribution', type_='model')
