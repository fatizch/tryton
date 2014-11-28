from trytond.pool import Pool
from .wizard import *


def register():
    Pool.register(
        StartFullContractRevision,
        module='endorsement_full_contract_revision_loan', type_='model')
