from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        ContractOption,
        LoanShare,
        Premium,
        module='contract_loan_invoice', type_='model')
