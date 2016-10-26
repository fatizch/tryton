# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .endorsement import *
from .wizard import *


def register():
    Pool.register(
        Contract,
        Endorsement,
        ChangeBillingInformation,
        ChangeDirectDebitAccount,
        module='endorsement_insurance_invoice_sepa', type_='model')
