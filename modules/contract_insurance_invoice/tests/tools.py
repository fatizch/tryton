# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model
from trytond.modules.account_invoice.tests.tools import create_payment_term


__all__ = ['create_billing_mode']


def create_billing_mode(frequency=None, payment_term_id=None,
        direct_debit=False):
    "Create billing mode"
    PaymentTerm = Model.get('account.invoice.payment_term')
    BillingMode = Model.get('offered.billing_mode')
    if not payment_term_id:
        payment_term = create_payment_term()
        payment_term.save()
    else:
        payment_term = PaymentTerm(payment_term_id)
    if not frequency:
        frequency = 'monthly'

    billing_mode = BillingMode(
        name=frequency,
        code=frequency,
        frequency=frequency)
    billing_mode.allowed_payment_terms.append(payment_term)
    if direct_debit:
        billing_mode.name = billing_mode.name + ' direct debit'
        billing_mode.code = billing_mode.code + '_direct_debit'
        billing_mode.direct_debit = True
        billing_mode.allowed_direct_debit_days = '5, 10, 15'
    billing_mode.save()
    return billing_mode


def add_invoice_configuration(product, accounts):
    payment_term = create_payment_term()
    payment_term.save()

    freq_monthly = create_billing_mode('monthly', payment_term.id)
    freq_quarterly = create_billing_mode('quarterly', payment_term.id)
    freq_monthly_direct_debit = create_billing_mode('monthly', payment_term.id,
        direct_debit=True)
    freq_yearly = create_billing_mode('yearly', payment_term.id)

    product.billing_modes.append(freq_monthly)
    product.billing_modes.append(freq_yearly)
    product.billing_modes.append(freq_quarterly)
    product.billing_modes.append(freq_monthly_direct_debit)

    for coverage in product.coverages:
        coverage.account_for_billing = accounts['revenue']
    return product
