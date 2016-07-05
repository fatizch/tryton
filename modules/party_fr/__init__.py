# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .address import *
from .party import *
from .test_case import *


def register():
    Pool.register(
        # from address
        Address,
        # from party
        Party,
        # from test_case
        TestCaseModel,
        module='party_fr', type_='model')
