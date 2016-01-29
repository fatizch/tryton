from trytond.pool import Pool
from .endorsement import *
from .wizard import *


def register():
    Pool.register(
        Contract,
        ChangeBillingInformation,
        ChangeDirectDebitAccount,
        module='endorsement_insurance_invoice_sepa', type_='model')
