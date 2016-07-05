# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .contract import *
from .rule_engine import *
from .event import *


def register():
    Pool.register(
        ContractSet,
        Contract,
        RuleEngineRuntime,
        ContractSetSelectDeclineReason,
        ReportTemplate,
        Configuration,
        EventTypeAction,
        EventLog,
        module='contract_set', type_='model')
    Pool.register(
        ContractSetDecline,
        module='contract_set', type_='wizard')
