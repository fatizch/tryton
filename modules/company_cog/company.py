from trytond.pool import PoolMeta

from trytond.modules.coop_utils import export

__metaclass__ = PoolMeta
__all__ = [
    'Company',
    ]


class Company(export.ExportImportMixin):
    __name__ = 'company.company'

    @classmethod
    def _export_keys(cls):
        return set(['party.name'])
