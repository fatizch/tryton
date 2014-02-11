from trytond.pool import PoolMeta

from trytond.modules.cog_utils import export

__metaclass__ = PoolMeta
__all__ = [
    'Company',
    ]


class Company(export.ExportImportMixin):
    __name__ = 'company.company'

    @classmethod
    def _export_keys(cls):
        return set(['party.name'])

    def get_publishing_values(self):
        result = self.party.get_publishing_values()
        return result
