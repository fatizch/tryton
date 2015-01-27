from trytond.pool import PoolMeta
from trytond.modules.cog_utils import export

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    ]


class Invoice(export.ExportImportMixin):
    __name__ = 'account.invoice'
    _func_key = 'number'

    @classmethod
    def is_master_object(cls):
        return True
