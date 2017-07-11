# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import test_case


def register():
    Pool.register(
        # From test_case
        test_case.TestCaseModel,
        module='account_insurance_fr', type_='model')
