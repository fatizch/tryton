# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import country
import zipcode
import test_case


def register():
    Pool.register(
        country.Country,
        country.CountrySubdivision,
        zipcode.Zip,
        test_case.TestCaseModel,
        module='country_cog', type_='model')
