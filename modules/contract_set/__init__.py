# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import contract
from .rule_engine import *
from .event import *


def register():
    Pool.register(
        contract.ContractSet,
        contract.Contract,
        rule_engine.RuleEngineRuntime,
        contract.ContractSetSelectDeclineReason,
        contract.ReportTemplate,
        contract.Configuration,
        event.EventTypeAction,
        event.EventLog,
        module='contract_set', type_='model')
    Pool.register(
        contract.ContractSetDecline,
        module='contract_set', type_='wizard')
