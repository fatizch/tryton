# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .distribution import *
from .configuration import *
from .party import *
from .res import *
from .contract import *
from .process import *
from .rule_engine import *


def register():
    Pool.register(
        DistributionNetwork,
        Configuration,
        Party,
        User,
        Contract,
        CoveredElement,
        Beneficiary,
        ContractBillingInformation,
        ContractSubscribeFindProcess,
        RuleEngineRuntime,
        module='distribution_portfolio', type_='model')
