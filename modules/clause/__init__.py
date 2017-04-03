# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import clause
import test_case


def register():
    Pool.register(
        clause.Clause,
        test_case.TestCaseModel,
        module='clause', type_='model')
