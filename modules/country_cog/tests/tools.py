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
