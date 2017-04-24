# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import payment
import batch


def register():
    Pool.register(
        payment.Group,
        payment.Payment,
        payment.PaymentCreationStart,
        payment.ProcessPayboxUrl,
        batch.PaymentAcknowledgeBatch,
        module='account_payment_paybox_cog', type_='model')
    Pool.register(
        payment.PaymentCreation,
        payment.ProcessPayment,
        module='account_payment_paybox_cog', type_='wizard')
