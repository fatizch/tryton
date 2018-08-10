# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import instalment_plan
import contract
import wizard
import invoice
import payment_term


def register():
    Pool.register(
        contract.Contract,
        instalment_plan.ContractInstalmentPlan,
        instalment_plan.ContractInstalmentPlanPayment,
        invoice.Invoice,
        wizard.InstalmentSelectPeriod,
        wizard.InstalmentScheduledPayments,
        payment_term.PaymentTerm,
        module='contract_instalment_plan', type_='model')
    Pool.register(
        wizard.CreateInstalmentPlan,
        module='contract_instalment_plan', type_='wizard')
