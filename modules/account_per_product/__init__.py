# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import move
from . import account
from . import party
from . import offered
from . import contract
from . import invoice
from . import payment
from . import statement
from . import commission
from . import claim
from . import insurer


def register():
    Pool.register(
        move.Move,
        move.MoveLine,
        move.ReconcileShow,
        move.MoveTemplate,
        move.MoveTemplateKeyword,
        move.MoveLineTemplate,
        account.AgedBalanceContext,
        offered.Product,
        offered.ProductOptionDescriptionRelation,
        contract.Contract,
        invoice.Invoice,
        party.Insurer,
        module='account_per_product', type_='model')
    Pool.register(
        payment.Journal,
        payment.Payment,
        module='account_per_product', type_='model',
        depends=['account_payment_cog'])
    Pool.register(
        statement.Statement,
        statement.Line,
        module='account_per_product', type_='model',
        depends=['account_statement_contract'])
    Pool.register(
        commission.Commission,
        commission.PlanLines,
        commission.Agent,
        module='account_per_product', type_='model',
        depends=['commission_insurance'])
    Pool.register(
        claim.Indemnification,
        module='account_per_product', type_='model',
        depends=['claim_indemnification'])
    Pool.register(
        insurer.InsurerSlipConfiguration,
        module='account_per_product', type_='model',
        depends=['commission_insurer'])
    Pool.register(
        account.AgedBalanceReport,
        module='account_per_product', type_='report')
    Pool.register(
        move.Reconcile,
        module='account_per_product', type_='wizard')
