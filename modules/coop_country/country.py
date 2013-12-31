from trytond.pool import PoolMeta

from trytond.modules.coop_utils import export

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


class CountrySubdivision(export.ExportImportMixin):
    'Country Subdivision'

    __name__ = 'country.subdivision'

    @classmethod
    def _export_keys(cls):
        return set(['code'])
