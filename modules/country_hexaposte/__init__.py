# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .zipcode import *
from .test_case import *
from .batch import *


def register():
    Pool.register(
        Zip,
        TestCaseModel,
        UpdateZipCodesFromHexaPost,
        module='country_hexaposte', type_='model')
