from trytond.pool import Pool

from .contract import *
from .rule_engine import *
from .party import *


def register():
    Pool.register(
        # from contract
        StatusHistory,
        Contract,
        SubscribedCoverage,
        ContractAddress,
        LetterModel,
        #From Rule Engine
        OfferedContext,
        ContractContext,
        # from party
        ContactHistory,
        module='contract', type_='model')
