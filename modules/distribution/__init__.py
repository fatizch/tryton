# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .distribution import *
from .test_case import *
import party


def register():
    Pool.register(
        DistributionNetwork,
        DistributionNetworkContactMechanism,
        party.Party,
        TestCaseModel,
        module='distribution', type_='model')
    Pool.register(
        party.PartyReplace,
        module='distribution', type_='wizard')
