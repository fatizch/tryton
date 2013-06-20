from trytond.pool import Pool

from .contract import *
from .rule_engine import *


def register():
    Pool.register(
        StatusHistory,
        Contract,
        SubscribedCoverage,
        ContractAddress,
        LetterModel,
        #From Rule Engine
        OfferedContext,
        ContractContext,
        module='contract', type_='model')
