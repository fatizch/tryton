# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import endorsement
import wizard
from trytond.pool import Pool


def register():
    Pool.register(
        endorsement.Loan,
        wizard.StartFullContractRevision,
        module='endorsement_full_contract_revision_loan', type_='model')
