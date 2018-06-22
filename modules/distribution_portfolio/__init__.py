# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import distribution
import configuration
import party
import contract
import process
import rule_engine
import res
import invoice
import move
import payment
import claim
import commission
import statement


def register():
    Pool.register(
        distribution.DistributionNetwork,
        configuration.Configuration,
        configuration.ConfigurationDefaultPortfolio,
        party.Party,
        party.ContactMechanism,
        party.PartyRelationAll,
        contract.Contract,
        contract.CoveredElement,
        contract.Beneficiary,
        contract.ContractBillingInformation,
        rule_engine.RuleEngineRuntime,
        res.User,
        invoice.Invoice,
        move.Line,
        statement.LineGroup,
        payment.Payment,
        payment.Mandate,
        payment.MergedPayment,
        claim.Claim,
        claim.Loss,
        commission.Commission,
        commission.AggregatedCommission,
        module='distribution_portfolio', type_='model')

    Pool.register(
        process.ContractSubscribe,
        module='distribution_portfolio', type_='wizard')
