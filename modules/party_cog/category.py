from trytond.pool import PoolMeta
from trytond.modules.cog_utils import export

__metaclass__ = PoolMeta

__all__ = [
    'PartyCategory',
    ]


class PartyCategory(export.ExportImportMixin):
    __name__ = 'party.category'
