# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import contract
import event
import wizard


def register():
    Pool.register(
        contract.Contract,
        contract.ContractRightSuspension,
        wizard.ContractSelectHoldReason,
        wizard.ContractActivateConfirm,
        module='contract_insurance_suspension', type_='model')
    Pool.register(
        wizard.ContractHold,
        wizard.ContractActivate,
        module='contract_insurance_suspension', type_='wizard')
    Pool.register(
        event.EventLog,
        module='contract_insurance_suspension', type_='model',
        depends=['event_log'])
