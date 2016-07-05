# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .company import *
from .res import *
from .test_case import *
from .ir import *
from .party import *


def register():
    Pool.register(
        Company,
        User,
        Employee,
        Sequence,
        SequenceStrict,
        TestCaseModel,
        PartyConfiguration,
        module='company_cog', type_='model')
