from trytond.pool import PoolMeta, Pool
from trytond.config import config

from trytond.modules.cog_utils import export

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
        country, = Country.search([('code', '=', code)])
        return country


class CountrySubdivision(export.ExportImportMixin):
    'Country Subdivision'

    __name__ = 'country.subdivision'
