# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model


def create_country(name=None, code=None):
    Country = Model.get('country.country')

    if not name:
        name = 'France'
    if not code:
        code = 'FR'
    countries = Country.find([('code', '=', code)])
    if not countries:
        country = Country(name=name, code=code)
        country.save()
    else:
        country, = countries
    return country
