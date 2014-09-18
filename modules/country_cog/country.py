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

    @classmethod
    def _export_keys(cls):
        return set(['code'])

    @classmethod
    def _export_force_recreate(cls):
        result = super(Country, cls)._export_force_recreate()
        result.remove('subdivisions')
        return result

    @staticmethod
    def default_country():
        Country = Pool().get('country.country')
        code = config.get('options', 'default_country', 'FR')
        country, = Country.search([('code', '=', code)])
        return country


class CountrySubdivision(export.ExportImportMixin):
    'Country Subdivision'

    __name__ = 'country.subdivision'

    @classmethod
    def _export_keys(cls):
        return set(['code'])
