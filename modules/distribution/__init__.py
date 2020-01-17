# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import distribution
from . import test_case
from . import party
from . import res
from . import api


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

    Pool.register(
        api.APIIdentity,
        api.User,
        api.APICore,
        module='distribution', type_='model', depends=['api'])

    Pool.register(
        api.DistributionNetwork,
        api.APIIdentityWebResources,
        module='distribution', type_='model',
        depends=['api', 'web_configuration'])
