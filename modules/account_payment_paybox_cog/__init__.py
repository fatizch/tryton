# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import payment
from . import batch
from . import wizard
from . import move
from . import account
from . import offered
from . import contract


def register():
    Pool.register(
        payment.Group,
        payment.Payment,
        payment.PaymentCreationStart,
        payment.ProcessPayboxUrl,
        batch.PaymentAcknowledgeBatch,
        move.MoveLine,
        account.Configuration,
        module='account_payment_paybox_cog', type_='model')
    Pool.register(
        payment.PaymentCreation,
        payment.ProcessPayment,
        wizard.CreatePayboxPayment,
        wizard.ProcessPayboxPayment,
        module='account_payment_paybox_cog', type_='wizard')
    Pool.register(
        contract.Contract,
        offered.Product,
        module='account_payment_paybox_cog', type_='model',
        depends=['contract_insurance_invoice'])
