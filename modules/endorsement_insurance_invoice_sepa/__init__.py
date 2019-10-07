# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import endorsement
from . import wizard
from . import api


def register():
    Pool.register(
        endorsement.Contract,
        endorsement.Endorsement,
        wizard.ContractDisplayer,
        wizard.ChangeBillingInformation,
        wizard.ChangeDirectDebitAccount,
        module='endorsement_insurance_invoice_sepa', type_='model')

    Pool.register(
        api.APIParty,
        api.APIEndorsement,
        module='endorsement_insurance_invoice_sepa', type_='model',
        depends=['api'])
