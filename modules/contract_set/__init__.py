from trytond.pool import Pool
from .contract import *
from .rule_engine import *


def register():
    Pool.register(
        ContractSet,
        Contract,
        RuleEngineRuntime,
        module='contract_set', type_='model')
