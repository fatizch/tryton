# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import zipcode
import test_case
import batch


def register():
    Pool.register(
        zipcode.Zip,
        test_case.TestCaseModel,
        batch.UpdateZipCodesFromHexaPost,
        module='country_hexaposte', type_='model')
