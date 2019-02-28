# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from . import contract
from . import configuration
from . import commission
from . import invoice
from . import event
from . import rule_engine
from . import wizard
from . import batch
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
        wizard.SimulateCommissionsParameters,
        wizard.SimulateCommissionsLine,
        batch.DesynchronizedPrepaymentReport,
        batch.DesynchronizedRedeemedReport,
        commission.CommissionDescriptionConfiguration,
        module='commission_insurance_prepayment', type_='model')
    Pool.register(
        commission.FilterCommissions,
        commission.FilterAggregatedCommissions,
        wizard.PrepaymentSync,
        module='commission_insurance_prepayment', type_='wizard')
