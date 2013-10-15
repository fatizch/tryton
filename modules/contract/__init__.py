from trytond.pool import Pool

from .contract import *
from .rule_engine import *
from .party import *
from .test_case import *


def register():
    Pool.register(
        # from contract
        StatusHistory,
        Contract,
        SubscribedCoverage,
        ContractAddress,
        DeliveredService,
        LetterModel,
        #From Rule Engine
        OfferedContext,
        ContractContext,
        # from party
        Party,
        ContactHistory,
        # from test_case
        TestCaseModel,
        module='contract', type_='model')
