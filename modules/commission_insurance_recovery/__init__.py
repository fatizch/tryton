# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
