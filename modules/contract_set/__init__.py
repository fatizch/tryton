from trytond.pool import Pool
from .contract import *
from .rule_engine import *


def register():
    Pool.register(
        ContractSet,
        Contract,
        RuleEngineRuntime,
        ContractSetSelectDeclineReason,
        ReportTemplate,
        Configuration,
        module='contract_set', type_='model')
    Pool.register(
        ContractSetDecline,
        module='contract_set', type_='wizard')
