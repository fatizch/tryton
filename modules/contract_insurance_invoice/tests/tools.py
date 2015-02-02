from proteus import Model
from trytond.modules.account_invoice.tests.tools import create_payment_term


__all__ = ['create_billing_mode']


def create_billing_mode(frequency=None, payment_term_id=None):
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
    billing_mode.save()
    return billing_mode


def add_invoice_configuration(product, accounts):
    payment_term = create_payment_term()
    payment_term.save()

    freq_monthly = create_billing_mode('monthly', payment_term.id)
    freq_yearly = create_billing_mode('yearly', payment_term.id)

    product.billing_modes.append(freq_monthly)
    product.billing_modes.append(freq_yearly)

    product.account_for_billing = accounts['revenue']
    for coverage in product.coverages:
        coverage.account_for_billing = accounts['revenue']
    return product
