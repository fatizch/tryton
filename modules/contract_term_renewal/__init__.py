from trytond.pool import Pool
from .rule_engine import *
from .offered import *
from .contract import *
from .batch import *
from .report_engine import *
from .wizard import *


def register():
    Pool.register(
        RuleEngine,
        Product,
        ProductTermRenewalRule,
        ActivationHistory,
        Contract,
        SelectDeclineRenewalReason,
        RenewContracts,
        ReportTemplate,
        TerminateContract,
        ConfirmRenew,
        module='contract_term_renewal', type_='model')
    Pool.register(
        DeclineRenewal,
        Renew,
        module='contract_term_renewal', type_='wizard')
