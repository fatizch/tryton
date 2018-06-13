# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import contract
import commission
import invoice
import party
import payment
import account
import batch
import test_case
import offered
import process
import distribution


def register():
    Pool.register(
        distribution.DistributionNetwork,
        contract.Contract,
        contract.ContractOption,
        commission.AggregatedCommission,
        commission.Commission,
        commission.PlanLines,
        commission.Plan,
        commission.PlanRelation,
        commission.PlanLinesCoverageRelation,
        commission.PlanCalculationDate,
        commission.Agent,
        offered.Product,
        offered.OptionDescription,
        invoice.InvoiceLine,
        invoice.Invoice,
        party.Party,
        commission.CreateAgentsParties,
        commission.CreateAgentsAsk,
        commission.CreateInvoiceAsk,
        commission.SelectNewBroker,
        payment.Configuration,
        account.Fee,
        account.MoveLine,
        commission.OpenCommissionsSynthesisStart,
        commission.OpenCommissionsSynthesisShow,
        commission.OpenCommissionSynthesisYearLine,
        batch.CreateCommissionInvoiceBatch,
        batch.PostCommissionInvoiceBatch,
        test_case.TestCaseModel,
        module='commission_insurance', type_='model')
    Pool.register(
        commission.CreateInvoice,
        commission.CreateAgents,
        commission.ChangeBroker,
        commission.FilterCommissions,
        commission.OpenCommissionsSynthesis,
        commission.FilterAggregatedCommissions,
        process.ContractSubscribe,
        module='commission_insurance', type_='wizard')
