# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import commission
import rule_engine
import contract


def register():
    Pool.register(
        commission.CommissionRecoveryRule,
        commission.Plan,
        commission.Commission,
        rule_engine.RuleEngineRuntime,
        contract.Contract,
        contract.ContractOption,
        module='commission_insurance_recovery', type_='model')
