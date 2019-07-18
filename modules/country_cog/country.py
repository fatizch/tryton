# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.config import config

from trytond.modules.coog_core import export, model

__all__ = [
    'Country',
    'CountrySubdivision',
    ]


class Country(model.CodedMixin, export.ExportImportMixin):
    __name__ = 'country.country'

    @staticmethod
    def _default_country():
        Country = Pool().get('country.country')
        code = config.get('options', 'default_country', default='FR')
        country = Country.search([('code', '=', code)])
        if country:
            return country[0]


class CountrySubdivision(export.ExportImportMixin):
    'Country Subdivision'

    __name__ = 'country.subdivision'

    def get_rec_name(self, name):
        res = super(CountrySubdivision, self).get_rec_name(name)
        return res + '(%s)' % self.code
