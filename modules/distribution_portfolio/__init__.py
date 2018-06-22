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
        rule_engine.RuleEngineRuntime,
        res.User,
        invoice.Invoice,
        move.Line,
        statement.LineGroup,
        payment.Payment,
        payment.Mandate,
        payment.MergedPayment,
        commission.Commission,
        commission.AggregatedCommission,
        module='distribution_portfolio', type_='model')

    Pool.register(
        process.ContractSubscribe,
        module='distribution_portfolio', type_='wizard',
        depends=['contract_process'])

    Pool.register(
        contract.CoveredElement,
        module='distribution_portfolio', type_='model',
        depends=['contract_insurance'])

    Pool.register(
        contract.Beneficiary,
        module='distribution_portfolio', type_='model',
        depends=['contract_life_clause'])

    Pool.register(
        contract.ContractBillingInformation,
        module='distribution_portfolio', type_='model',
        depends=['contract_insurance_invoice'])

    Pool.register(
        claim.Claim,
        claim.Loss,
        module='distribution_portfolio', type_='model',
        depends=['claim'])
