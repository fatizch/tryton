# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import contract
import loan


def register():
    Pool.register(
        contract.Contract,
        loan.Loan,
        module='loan_apr_fr', type_='model')
