# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import rule_engine
from . import offered
from . import contract
from . import batch
from . import report_engine
from . import wizard


def register():
    Pool.register(
        rule_engine.RuleEngine,
        offered.Product,
        offered.ProductTermRenewalRule,
        contract.ActivationHistory,
        contract.Contract,
        contract.SelectDeclineRenewalReason,
        batch.RenewContracts,
        report_engine.ReportTemplate,
        contract.ConfirmRenew,
        module='contract_term_renewal', type_='model')
    Pool.register(
        contract.DeclineRenewal,
        contract.Renew,
        module='contract_term_renewal', type_='wizard')
    Pool.register(
        wizard.TerminateContract,
        module='contract_term_renewal', type_='model',
        depends=['endorsement'])
