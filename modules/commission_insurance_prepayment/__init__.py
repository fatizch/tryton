# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import contract
import configuration
import commission
import invoice
import event
import rule_engine
import wizard
import batch
from trytond.pool import Pool


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationTerminationReason,
        contract.Contract,
        contract.ContractOption,
        commission.PlanLines,
        commission.Commission,
        commission.Plan,
        commission.Agent,
        commission.AggregatedCommission,
        invoice.Invoice,
        event.Event,
        rule_engine.RuleEngineRuntime,
        wizard.PrepaymentSyncShowRedeemedInconsistency,
        wizard.PrepaymentSyncShowDisplayer,
        wizard.PrepaymentSyncResult,
        wizard.PrepaymentSyncShow,
        batch.DesynchronizedPrepaymentReport,
        batch.DesynchronizedRedeemedReport,
        module='commission_insurance_prepayment', type_='model')
    Pool.register(
        commission.FilterCommissions,
        commission.FilterAggregatedCommissions,
        wizard.PrepaymentSync,
        module='commission_insurance_prepayment', type_='wizard')
