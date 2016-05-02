from trytond.pool import PoolMeta
from trytond.modules.cog_utils import export

__metaclass__ = PoolMeta
__all__ = [
    'Country',
    'CountrySubdivision',
    ]


class Country(export.ExportImportMixin):
    __name__ = 'country.country'
    _func_key = 'code'


class CountrySubdivision(export.ExportImportMixin):
    'Country Subdivision'

    __name__ = 'country.subdivision'
