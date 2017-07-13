# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import rule_engine
import offered
import contract
import batch
import report_engine
import wizard


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
        wizard.TerminateContract,
        contract.ConfirmRenew,
        module='contract_term_renewal', type_='model')
    Pool.register(
        contract.DeclineRenewal,
        contract.Renew,
        module='contract_term_renewal', type_='wizard')
