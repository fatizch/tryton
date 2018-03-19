# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import distribution
import test_case
import party
import res


def register():
    Pool.register(
        distribution.DistributionNetwork,
        distribution.DistributionNetworkContactMechanism,
        party.Party,
        res.User,
        test_case.TestCaseModel,
        module='distribution', type_='model')
    Pool.register(
        party.PartyReplace,
        module='distribution', type_='wizard')
