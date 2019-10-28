# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import contract
from . import loan
from . import api


def register():
    Pool.register(
        contract.Contract,
        contract.ContractLoan,
        loan.Loan,
        module='loan_apr_fr', type_='model')
    Pool.register(
        api.APIContract,
        module='loan_apr_fr', type_='model',
        depends=['api'])
