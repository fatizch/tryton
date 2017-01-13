# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import country
import address


def register():
    Pool.register(
        country.Country,
        country.CountryAddressLine,
        address.Address,
        module='country_address_configuration', type_='model')
