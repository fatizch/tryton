from trytond.pool import Pool
from .wizard import *


def register():
    Pool.register(
        ChangeBillingInformation,
        module='endorsement_insurance_invoice_sepa', type_='model')
