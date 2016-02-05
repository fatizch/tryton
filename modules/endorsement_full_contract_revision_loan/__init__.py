from trytond.pool import Pool
from .endorsement import *
from .wizard import *


def register():
    Pool.register(
        Loan,
        StartFullContractRevision,
        module='endorsement_full_contract_revision_loan', type_='model')
