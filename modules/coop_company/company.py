from trytond.pool import PoolMeta

from trytond.modules.coop_utils import export

__all__ = [
    'Company',
]

__metaclass__ = PoolMeta


class Company(export.ExportImportMixin):
    'Company'

    __name__ = 'company.company'

    @classmethod
    def _export_keys(cls):
        return set(['party.name'])
