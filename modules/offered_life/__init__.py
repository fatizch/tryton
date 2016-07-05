# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .offered import *
from .salary_range import *
from .test_case import *


def register():
    Pool.register(
        # from offered
        OptionDescription,
        # from salary_range
        SalaryRange,
        SalaryRangeVersion,
        # from test_case
        TestCaseModel,
        module='offered_life', type_='model')
