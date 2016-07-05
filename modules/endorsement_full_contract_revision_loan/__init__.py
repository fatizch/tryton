# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .endorsement import *
from .wizard import *


def register():
    Pool.register(
        Loan,
        StartFullContractRevision,
        module='endorsement_full_contract_revision_loan', type_='model')
