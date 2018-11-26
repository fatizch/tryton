# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import contract
from . import rule_engine
from . import event


def register():
    Pool.register(
        contract.ContractSet,
        contract.Contract,
        rule_engine.RuleEngineRuntime,
        contract.ContractSetSelectDeclineReason,
        contract.ReportTemplate,
        contract.Configuration,
        contract.ConfigurationContractSetNumberSequence,
        event.EventTypeAction,
        module='contract_set', type_='model')
    Pool.register(
        contract.ContractSetDecline,
        module='contract_set', type_='wizard')

    Pool.register(
        event.EventLog,
        module='contract_set', type_='model',
        depends=['event_log'])
