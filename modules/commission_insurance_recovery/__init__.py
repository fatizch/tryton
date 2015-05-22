from trytond.pool import Pool
from .commission import *
from .rule_engine import *
from .contract import *


def register():
    Pool.register(
        CommissionRecoveryRule,
        Plan,
        Commission,
        RuleEngineRuntime,
        Contract,
        ContractOption,
        module='commission_insurance_recovery', type_='model')
