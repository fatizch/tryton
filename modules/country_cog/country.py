# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import export
from trytond.config import config

__metaclass__ = PoolMeta
__all__ = [
    'Country',
    'CountrySubdivision',
    ]


class Country(export.ExportImportMixin):
    __name__ = 'country.country'
    _func_key = 'code'

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
